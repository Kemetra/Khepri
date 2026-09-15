# S1-02 — Caller-controlled identifiers and security material at store seams

**Authority:** none required. `S1-02`'s deliverable is a *ranked list*; §17 admits S1 triage as
parallel-safe work that "may proceed if it does not overlap CAL1 files". This note writes no code
and touches no CAL1 hotspot.

**Date:** 2026-09-15. **Measured against:** `ff29dcf` (`main`).

**What this is not.** It is not `S1-03` (select one bounded family) and not an owner decision. Every
rank below is a reading of shipped code; the two that need authority say so, and nothing here
authorizes a fix.

**Its `#231` clause is discharged.** The roadmap row records that the live-authorization evidence was
delivered directly rather than through this triage, so this ranks *store seams only*.

---

## 0. What a "store seam" is here, and why the ranking is narrow

A store seam is a point where a value the caller supplies becomes a persisted identifier or a
security material, with no database-level constraint standing behind the Python that checked it.
The ranking is by **what the database would still accept if the Python layer above it were wrong**,
not by how alarming the code reads.

That criterion is what separates rank 1 from the rest: four of the seams below are already
unrepresentable at the schema level, and their residual risk is a *write path*, not a *shape*.

---

## 1. `rra_beta_sessions.owner_id` is unanchored — the root of the RRA scope tree

**Rank 1. The only seam where the database can represent a cross-scope row.** Tracked as `#432`.

| Claim | Verified at |
|---|---|
| `owner_id` is an unconstrained `String`, not an FK | `src/khepri/rra/persistence.py:80` (`Mapped[str] = mapped_column(String, nullable=False)`) |
| No RLS, no tenant role, no `SET LOCAL`, no `current_setting` | `grep` over `src/` and `migrations/` returns nothing |
| A valid FK target exists | `rca_isolation_scopes` carries `uq_rca_scope_owner` on `owner_id` (`src/khepri/rca/persistence.py:355`) |
| Isolation is decided one layer up, in Python | `src/khepri/rra/sessions.py:77-111`; the module says so in its own docstring |

**The gap is narrower than `#432` frames it, and the correction matters for ranking.** RRA content
does *not* dangle: four content tables bind `(owner_id, session_id)` compositely to
`rra_beta_sessions` (`persistence.py:123`, `164`, `217`, `261`), so content attached to a *valid*
session under a *different* scope is already unrepresentable. This is the same seal
`rca/workspace/schema.py` applies with eight `ForeignKeyConstraint`s.

So the exposure is exactly one level deep: **forge the session row and everything beneath it
validates.** The composite FKs faithfully bind children to a parent whose own `owner_id` no
constraint vouches for.

**Why this is not a migration anyone may simply write.** `khepri.rra` imports nothing from
`khepri.rca` (`grep` for `from khepri.rca` under `src/khepri/rra/` returns nothing), and the two
packages declare **separate** `DeclarativeBase` metadata trees (`rra/persistence.py:41`,
`rca/persistence.py:62`). A foreign key from `rra_beta_sessions.owner_id` to
`rca_isolation_scopes.owner_id` crosses that boundary and couples the two metadata trees — which is
a construction-boundary decision of exactly the kind `#152` is about, not a local schema edit.

**Recommended disposition:** the strongest candidate for `S1-03`, *and* the one that needs its scope
named first. Three shapes exist and the choice is the owner's:

1. **Cross-package FK** — strongest guarantee, couples the metadata trees.
2. **A CHECK or trigger local to `khepri.rra`** — keeps the boundary, weaker guarantee, needs the
   scope table readable from the RRA connection anyway.
3. **RLS with a tenant role and `SET LOCAL`** — strongest of all and the largest change; the
   runtime user is currently the database owner `khepri`, so this is an operations change too.

Do not let a slice pick one by convenience. Which shape is admissible is a boundary reading.

---

## 2. Worker workbook directory does not reuse the hardened directory helper

**Rank 2. Caller-controlled path, already-solved shape, no cross-package question.** Listed as item 5
of `#434`.

Comparisons build their render directory through `_own_render_directory`, which sets mode `0o700`,
refuses a symlink, and refuses a foreign uid (`src/khepri/runtime/wiring.py:344-357`). The worker's
workbook directory defaults to `/tmp/khepri-workbooks` (`src/khepri/runtime/worker.py:42`) and is
created with `mkdir(..., exist_ok=True)` carrying none of those checks (`wiring.py:782`).

Inside the single-user image this is weak rather than exploitable; on a shared host it is customer
workbook exposure. **This is the cleanest `S1-04` candidate in the list**: the fix is to reuse a
helper that already exists in the same module, the accidental-bypass test is a directory
pre-created with a foreign uid or as a symlink, and it needs no new authority because it changes no
schema and no governed contract.

---

## 3. `owner_id` reaches the object store as a path component

**Rank 3. Caller-controlled identifier crossing into a second namespace.**

`delete_object_metadata(database, row.owner_id, row.session_id)` (`rra/persistence.py:792`) shows
the scope key addressing object storage as well as rows. The value is opaque by `FR-031`..`FR-035`,
which is what makes it safe to place in a path — but that safety is a *property of the generator*,
not a check at this seam. If rank 1 is ever fixed by anything weaker than a constraint, this is the
second surface that inherits the forged value.

**Recommended disposition:** not its own slice. Fold its assertion into whatever slice closes rank 1
— a test that a scope key containing a path separator or a traversal segment cannot be persisted.

---

## 4. Seams inspected and found already sealed

Recorded so a later triage does not re-rank them, per the lesson that a partial ledger sends a slice
to redo landed work.

- **RRA content → session** — composite `(owner_id, session_id)` FKs at `persistence.py:123`, `164`,
  `217`, `261`. Cross-scope content under a valid session is unrepresentable.
- **RCA workspace** — eight `ForeignKeyConstraint`s in `rca/workspace/schema.py`, plus
  `_refuse_identity_change` (`schema.py:810-823`), which refuses a scope reassignment one statement
  *earlier* than the composite key would. `#370`'s review found the reassignment hole and closed it
  both ways.
- **Session cookie** — `SameSite=Strict` (`rca/session_cookie.py:64-70`) is the real CSRF control,
  which is why `#434` item 2 is a fail-open *question* rather than an open door.

---

## 5. What this triage deliberately does not rank

`#434`'s items 1, 3, 4 and 6 (inflate cap, rate limit, `sslmode`, purge race) are real and are
tracked there. They are **not store seams**: none of them is a caller-controlled identifier becoming
a persisted value. Ranking them here would widen `S1-02` past its own row and duplicate an issue
that already holds them with better detail.

`#152` is the construction-boundary stance over `khepri.rra` records and is `S1-05`'s to close. This
note supplies one input to it — rank 1 is the record whose invariant a direct store caller can
violate — and closes nothing.

---

## 6. Recommended order for `S1-03`

1. **Rank 2 (worker directory)** if the goal is a bounded, shippable slice now: no authority
   question, an existing helper to reuse, a clean accidental-bypass test.
2. **Rank 1 (`owner_id` anchoring)** if the goal is the highest-value seam: it is the only one the
   database can misrepresent, but it needs the owner to name which of the three shapes is admissible
   before any code is written.

Rank 1 is more important. Rank 2 is more available. That is the whole trade, and picking between
them is a scheduling call rather than a technical one.
