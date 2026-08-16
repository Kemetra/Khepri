# R7-02 — a schema conflict that blocks the bridge, found before writing it

**Task:** `R7-02` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.
**Status:** finding. No code. `R7-02` is **blocked** and `KHEPRI-DEC-019` needs a supersession or an
amendment only the owner can make.

---

## 1. The finding, stated first

`KHEPRI-DEC-019` (`00e0f47`) admits an additive `RRA` entry point that creates an analysis session
against a caller-supplied opaque `owner_id`, and §5 of that record forbids any schema or migration.

**Those two clauses cannot both hold.** `rra_beta_sessions.owner_id` carries a `UNIQUE` constraint,
so one `owner_id` backs **exactly one session, ever**. A commercial organization holds one stable
`owner_id` for its lifetime (`FR-035`), so its second analysis is refused by the database.

The entry point can be written. The second call fails.

## 2. The evidence

Three constraints, read from the ORM and confirmed against the migration that created them
(`migrations/versions/20260729_0001_rra_sessions.py:46`):

```
rra_beta_sessions   UNIQUE (owner_id)                 <- one session per scope, ever
rra_beta_sessions   UNIQUE (owner_id, session_id)     <- redundant given the above
rra_uploads         UNIQUE (session_id)               <- one upload per session
```

The chain is therefore **one `owner_id` → one session → one upload**. `RRA` is architecturally
single-analysis-per-scope.

Verified by probe rather than by reading, because a schema claim deserves the same standard as a
test claim. Writing two sessions under one `owner_id` against the real metadata:

```
first session under the org's owner_id: OK
second session REFUSED: IntegrityError — UNIQUE constraint failed: rra_beta_sessions.owner_id
```

**This is coherent for the beta and only for the beta.** A participant redeems an invitation, gets
a throwaway scope, analyses one workbook, and the content expires in seven days. `RRA-001` never
promised more, and nothing here is a defect in `RRA`.

## 3. Why the obvious readings do not rescue it

**"One long-lived session per organization."** `R7-01` §4 describes resume as looking up an existing
session rather than creating one, which would need only one row. But `rra_uploads` declares
`UNIQUE (session_id)`, so that single session accepts exactly one upload — the organization gets one
analysis for its lifetime. This was the reading most likely to save the slice, and the upload
constraint closes it.

**"`FR-035` means RCA sessions, not RRA sessions."** The requirement reads: "one organization MUST
resolve to a stable scope **across sessions**, across active-organization switches, and across
membership changes." Even on the narrow reading, `FR-036` requires every retail fact a commercial
actor sees to originate from the existing `RRA` fact package — so a tenant that can run one analysis
ever is not a commercial product, whichever session the clause names.

**"Delete and recreate."** `RRA-002`'s deletion is immediate and idempotent, so a scope could in
principle be freed and reused. This is not proposed: it destroys the previous analysis to permit the
next one, and `R7`'s non-goals forbid changed retention. Recorded so the next reader does not have
to re-derive why it was rejected.

## 4. What `R7-02` did not do, deliberately

- **No migration.** `KHEPRI-DEC-019` §5 forbids schema changes, and the table belongs to `RRA`.
  Dropping a `UNIQUE` constraint on a governed table is not a slice's decision to take.
- **No amendment to `KHEPRI-DEC-019`.** Supersession is whole-document, and the record is governing
  as of `00e0f47`. Editing it to admit what it forbids would be authoring the owner's decision.
- **No entry point.** Writing a function whose second call raises `IntegrityError` would satisfy the
  slice's letter and ship a defect.
- **No `test_rra*` edit.** `KHEPRI-DEC-019` §4.1 makes that a conflict to record rather than resolve,
  and this is the record.

## 5. What the owner is being asked to choose between

Each option is a change to a governed artifact, so none is mine.

| Option | What it costs |
|---|---|
| **A. Drop `UNIQUE (owner_id)`** from `rra_beta_sessions`, keeping `UNIQUE (owner_id, session_id)` | One migration on an `RRA` table. The composite constraint already expresses the real invariant — the column-level one is what makes the scope single-use. **Smallest change that unblocks `R7`**; recommended. |
| **B. Also relax `rra_uploads.UNIQUE (session_id)`** | Needed only if one session should hold many analyses. Larger, and `R7-01` §4's create-once/resume-thereafter shape does not require it if A is taken. |
| **C. Commercial tenants get their own content tables** | `FR-036` forbids it — every retail fact must originate from the existing `RRA` package — and it duplicates the analysis pipeline. |
| **D. Accept one analysis per organization** | Not a commercial product. Recorded for completeness. |

**Option A is the recommendation, and the reasoning is that the two constraints disagree about what
is unique.** `UNIQUE (owner_id, session_id)` says a scope may hold many sessions and each pairing is
distinct; `UNIQUE (owner_id)` says it may hold one. The second is a beta assumption encoded as an
invariant, and it is the one `RRA-001`'s "only future attachment point for separately approved
commercial authentication" clause did not anticipate.

Taking A means `KHEPRI-DEC-019` §5's "no schema or migration" clause is wrong as written and needs
superseding — the decision authorized a shape that its own constraints forbid. That is a finding
about the record, not about the implementer, and it is why this note exists rather than a PR that
quietly widened the decision.

## 6. What is not blocked

- **`R7-04`** (preserve `RRA` independence and beta mode) is regression-only and touches no seam. It
  asserts the existing journey is unchanged for a participant with no account, which is true today
  and must remain true under every option above.
- **`R7-01`'s contract** stands. Nothing in §2, §3, or §4 is invalidated: the bridge still resolves
  an organization to its stable `owner_id` and hands only that across the boundary. The blocked part
  is persistence, not the contract.
