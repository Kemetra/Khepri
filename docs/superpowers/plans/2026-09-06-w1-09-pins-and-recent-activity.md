# `W1-09` — Pins and recent activity

> **Design, not authority.** The governing artifacts are active `KHEPRI-DEC-034` and `RCA-005`
> `FR-128`/`FR-129`. This document decides *how* to build what they authorize; it decides nothing
> about *whether*, and it amends nothing. Drafted by automation, which checks facts and consistency
> and does not approve changes (Constitution I).

**Date:** 2026-09-06
**Slice:** `W1-09`, the last unbuilt task in the `M3` workspace chain
**Authority:** `KHEPRI-DEC-034` (`active`), `RCA-005` `FR-128`, `FR-129`
**Branch:** `feat/w1-09-pins-and-recent-activity`, off `main` at `1d8c5de`

---

## 1. Why this slice could not start until now, and can now

`W1-01` through `W1-08` and `W1-10` merged between 2026-09-04 and 2026-09-06 (`#368`–`#385`).
`W1-09` was the remainder, and it was not unbuilt because it is hard.

**It had no authority.** `RCA-005` runs `FR-108`–`FR-127` and named no requirement for it, while its
Exclusions barred both halves: product telemetry for the activity feed, and no matrix row admitting
a per-account pin. `#386` (`1d8c5de`) closed that gap by authoring `KHEPRI-DEC-034` as a **new**
Constitution VII decision rather than an amendment to `KHEPRI-DEC-015` §3, and `RCA-005` gained
`FR-128` and `FR-129`. `#389` is housekeeping on the banners; the registry has read `state: active`
since the merge, and Constitution III makes the registry authoritative.

**The consequence for this slice is a boundary, not a licence.** `KHEPRI-DEC-015` §3 is unamended.
`W1-11` and `R8-08` stay excluded, and nothing built here is precedent for either.

## 2. The asymmetry that is the whole design

`FR-128` and `FR-129` look like one feature and are not. One writes; the other must not.

| | Pin (`FR-128`) | Recent activity (`FR-129`) |
|---|---|---|
| New retained data | One row per pin | **None** |
| Migration | Yes, `20260906_0029` | No |
| Deletion-matrix entry | Required | N/A — no table |
| `FR-125` audit event | **No**, by `FR-128` | No |
| Ends when | Object ends, pin removed, or organization ends | n/a — the view holds nothing to end |

`KHEPRI-DEC-034` §1 states it directly: *"The activity view retains nothing. It is a query over
dataset versions and analysis runs the workspace already stores under `KHEPRI-DEC-033`, ordered by
instants those records already carry. This is the whole of why it needs no telemetry: a view that
stores no event is not an event stream."*

**The door this closes in advance.** `FR-125` already retains a content-free audit event for every
workspace action, twelve months. Rendering *those* as the activity feed would be technically easy
and would claim no new data. `RCA-005` forbids it: the audit carve-out *"does not reach"* product
use, and *"an audit event that begins to carry a product metric has become telemetry and is
excluded."* This design reads the workspace records themselves, never the audit table.

## 3. What gets built

### 3.1 `WorkspacePinRow` — `khepri/rca/workspace/schema.py`

Table `rca_workspace_pins`. `FR-128` enumerates the fields and closes the list with **"and nothing
else — no count, no access record, no ordering weight."** So the column set is exactly:

- the scope key (`RCA-001` `FR-031`–`FR-035`'s opaque isolation key, as every workspace table)
- `owner_id`
- `object_id` — opaque
- `object_kind` — dataset version or analysis run
- `pinned_at`

A `UNIQUE (owner_id, object_id)` constraint makes pinning idempotent **at the schema**, not in a
read-then-write sequence. Two concurrent pins of the same object then resolve in the database rather
than racing in the service, which is the shape `FR-127`'s concurrent case asks for.

### 3.2 Migration `20260906_0029_rca_workspace_pins.py`

Chained onto `20260906_0028` (`W1-07b`'s sweep action), which is head.

**The head is pinned in three places and all three move together:**

1. `RCA_REVISIONS` in `tests/test_rca001_migration.py` — the middle field is the **migration file's
   slug, not the table**. This slice creates a table, so unlike `0026` and `0028` (CHECK rewrites)
   it also adds `rca_workspace_pins` to `RCA_TABLES`. That set is compared for **equality**, so
   omitting it fails rather than passing vacuously — the `#240` defect the comments there record.
2. `test_the_head_is_the_session_revision` in `tests/test_rca001_session_persistence.py:402`, whose
   docstring says the pin *"is updated by each slice that adds a migration, which is what forces
   that slice to notice it is now the one in flight."*
3. `STATUS.md`'s header.

One head. No downgrade that cannot run.

### 3.3 `deletion_matrix.py` — `"rca_workspace_pins": ENDING_CASCADE`

`KHEPRI-DEC-034` §1's matrix gives the pin row: *"The object ends, or the pin is removed, or the
organization ends"* → *"Row deleted, no tombstone"*, cascading from the pinned object's deletion.
That is `ENDING_CASCADE`.

**This entry is not bookkeeping — an existing test demands it.**
`test_every_workspace_table_has_exactly_one_stated_ending` compares `ENDINGS` against
`Base.metadata`, so the new table fails that test until its ending is stated. `deletion_matrix.py`'s
own docstring explains why it is built that way: *"A hand-written cascade is a scope that disarms
itself: a class added later that the sequence does not mention ends nothing, while every existing
test still passes."* This slice is the first to arrive after that guard and confirms it fires.

No tombstone. A pin is a stated preference, not content, and `KHEPRI-DEC-033` §3's allowlist governs
what survives a deletion — a pin survives nothing.

### 3.4 `store.py` — three verbs

`pin`, `unpin`, `pins_for_scope`. The cascade rides the **existing** `set_retention_state` walk
rather than a second one: `deletion_matrix.py` warns that re-implementing the walk is the second
implementation `local/sweeper.py` cautions against. Deleting a dataset version removes its pins in
the same transaction that tombstones it.

### 3.5 `khepri/runtime/shell_pins.py` — its own module

Following `shell_deletion.py` exactly (`offers_pins`, `add_pin_routes`), because `W1-07a` recorded
that a mutating route grown inside `shell_api.py` was the thing to avoid. `shell_api.py` dispatches
read surfaces; mutating routes live beside `shell_invitations.py`, `shell_artifact_handoff.py` and
`shell_deletion.py`.

Two POST routes, toggle-shaped, carrying the same CSRF and owner-resolution posture as the deletion
route. A pin is **owner-scoped**: `FR-128` says *"in their own scope"*, so the pin of one owner is
not visible to another in the same organization.

### 3.6 Surfaces — `shell_workspace.py`, `overview.html.j2`, `shell_copy.py`

Two new sections on the Overview surface `W1-05` built: **Pinned**, then **Recent activity**. The
pin control renders on the Data and Analyses rows. Bilingual strings in `shell_copy.py`.

Recent activity is read at request time from `rca_workspace_dataset_versions` and
`rca_workspace_analysis_runs`, ordered by the instants those rows already carry, and bounded to a
fixed small count. **It writes nothing to answer the question.**

## 4. What is deliberately not built

Each of these is refused by `KHEPRI-DEC-034` §2 or `RCA-005`'s Exclusions:

- No counter, frequency, access record, "opened N times", "most used", "trending", or ordering
  weight. Recency is an ordering over records that exist; frequency requires a record of each visit,
  which is the thing not authorized.
- No `FR-125` audit event for a pin, and **no new member of `AUDIT_ACTIONS`** — `FR-128` says so
  literally.
- No product-telemetry event of any kind. `KHEPRI-DEC-015` §3 stays unamended.
- No inactivity expiry. `KHEPRI-DEC-033` §4 decided against it.
- No claim on any surface that content expires automatically beyond what `KHEPRI-DEC-033` §5's
  caution permits.
- No change to admission, derivation, bundle assembly, rendering, the catalog routes, or the `/beta`
  journey.
- No figure computed, rounded or summed on a workspace surface.

## 5. Verification

`RCA-005`'s Verification section names the guard this slice must carry, and it is listed first.

### 5.1 The widening guard (`RCA-005` Verification, literally)

*"A test that `FR-128`/`FR-129` write no access record, counter or telemetry event, and that a pin
emits no audit event — the guard against `KHEPRI-DEC-034` being widened by implementation."*

Exercise both capabilities, then assert:

- no row was added to `rca_workspace_audit_events` or any telemetry sink;
- `AUDIT_ACTIONS` gained no member. A vocabulary is pinned in three places — the tuple, the
  closed-set test in `test_w104_audit_events.py`, and the migration's CHECK literal — and this
  asserts none of them moved.

### 5.2 Column extent, not subset

Assert the **emitted schema's** column set *equals* the permitted fields, read through
`inspect(...)` as `W1-02` established, because a dataclass field-set equality stays green while a
column is added to the table. Equality, not `>=`: a subset assertion cannot see a `view_count` added
later, which is precisely the widening §5.1 exists to prevent.

### 5.3 Isolation writes two scopes and reads one

`W1-02`'s convention: with one organization's rows in the table, an unfiltered query returns exactly
what a filtered one does, so a single-scope test cannot see a missing `WHERE`. Two scopes, read one,
assert the uniform denial byte-for-byte for the cross-scope read.

### 5.4 The activity view retains nothing

Count rows in **every** workspace table before and after rendering the Overview surface; assert
equality. This is the executable form of `FR-129`'s *"MUST retain nothing"*, and it is what
distinguishes the view from an event stream.

### 5.5 Cascade

Pin a dataset version, delete it through the real deletion route, assert the pin is gone — driven
through the production verb, not raw SQL, so a mutant of the bypassed verb cannot survive.

### 5.6 Ordinary cases

Pin round-trips; unpin is idempotent; a second pin of the same object is a no-op rather than an
error; activity ordering is by the recorded instants; both surfaces render in both languages with
RTL parity.

### 5.7 Gates

`khepri-gov validate`, `ruff check` and `pytest` green; CodeScene at the repository threshold.
The whole suite runs, not the targeted one — changing a field's meaning breaks suites never opened.

## 6. Sequencing

One PR, two commits: plan + RED tests, then implementation.

Its first commit also corrects roadmap §16's `W1` row and §17 item 17, which still read
`READY_FOR_PLAN — next: W1-01` and describe nine slices while ten IDs merged. Folding that
correction into this PR rather than a concurrent docs PR is deliberate: a code merge falsifies a
docs PR's tree-state claims, and this is the slice that closes the chain those rows describe.

## 7. Open questions

None blocking. Two design choices were taken in session and are recorded here rather than left
implicit:

1. **The activity view surfaces on Overview only**, not as its own route — Overview is where
   "what did I last work on" belongs, and a fourth destination would add a nav entry, a template and
   a parity surface for a convenience feature.
2. **Pins get both a control and a gathered list** — a pin control on Data and Analyses rows, and a
   Pinned section on Overview. `KHEPRI-DEC-034` §1 states the purpose as *"quick return"*, which an
   ordering-only treatment serves weakly.
