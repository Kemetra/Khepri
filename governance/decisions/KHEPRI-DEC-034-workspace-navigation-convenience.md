# KHEPRI-DEC-034: Workspace navigation convenience — pins and recent activity

> **PROPOSED.** Under Constitution II a change is proposed while it exists only on a branch or pull
> request, and becomes governing when the sole owner merges it. This document is drafted for the
> owner's decision and is **not** approved by its own existence. It was drafted by automation, which
> checks facts and consistency and does not approve changes (Constitution I).

## Context

`W1-09` — *"add favorites/pins and recent activity without creating a new calculation"* — is the one
remaining unbuilt task in the M3 workspace chain. Every other slice, `W1-01` through `W1-08` and
`W1-10`, has merged. `W1-09` cannot begin, and the reason is not that it is hard.

**It has no authority.** `RCA-005` is the active `G3` specification governing the workspace, and it
runs `FR-108`–`FR-127`. `FR-123`/`FR-124` are `W1-07`'s, `FR-125` is the audit event, `FR-127` names
`W1-10` literally. **No requirement in `RCA-005` names `W1-09`**, and `G3-04`'s plan allocates ten
slices without one for it. A slice built on it would be "outside its specification within the meaning
of Constitution IV".

**And both halves are excluded**, which is why this is a decision rather than a specification
amendment alone:

- **Recent activity.** `RCA-005` Exclusions bar *"Any product-telemetry event"*, and record that
  `W1-11`'s repeat-use telemetry *"waits for an owner-authored amendment to `KHEPRI-DEC-015` §3,
  exactly as `R8-08` does."* `KHEPRI-DEC-015` §3 lists **product analytics** among the purposes that
  retention never authorizes, and says a new purpose *"is new data use and requires its own
  Constitution VII decision."* This document is that decision, or it is nothing.
- **Pins.** A per-account, per-object preference is new retained data about a person's behaviour. It
  is not covered by any row of `KHEPRI-DEC-015` §2's identity matrix or `KHEPRI-DEC-033` §2's content
  matrix, and `KHEPRI-DEC-015` §4 forbids retaining a field *"because it may become useful later."*

**The narrow reading this decision takes.** `FR-125` already requires a content-free audit event for
every workspace action, retained twelve months. It would be technically possible to render those
events as an activity feed and claim no new data. `RCA-005` closes that door in advance: the audit
carve-out *"does not reach"* product use, and *"an audit event that begins to carry a product metric
has become telemetry and is excluded."* Reusing the audit trail as a customer-facing feed is exactly
the conversion that sentence forbids, so this decision does not attempt it.

## Decision

### 1. What is authorized

Two capabilities, each with one row in the matrix below, and nothing beyond them.

| Class | Purpose | Retained | End trigger | Post-trigger | Deletion | Backup | Anchor |
|---|---|---|---|---|---|---|---|
| Workspace pin | Let an owner mark a dataset version or analysis for quick return | `owner_id`, opaque object identifier, object kind, pinned-at instant | The object ends, or the pin is removed, or the organization ends | Row deleted, no tombstone | Immediate and idempotent on demand; cascades from the pinned object's deletion | `KHEPRI-DEC-033` §4's fourteen days | This decision |
| Recent activity view | Show an owner what they last worked on, so returning to work does not require search | **Nothing new.** Derived at read time from workspace records the scope already holds | n/a — no new row | n/a | n/a — deleting the underlying record removes it from the view | n/a | This decision |

**The activity view retains nothing.** It is a query over dataset versions and analysis runs the
workspace already stores under `KHEPRI-DEC-033`, ordered by instants those records already carry.
This is the whole of why it needs no telemetry: a view that stores no event is not an event stream.

### 2. What is not authorized, and stays not authorized

- **No product-telemetry event.** `KHEPRI-DEC-015` §3 is **not amended** by this decision. Product
  analytics remains an unauthorized purpose, `W1-11` remains excluded, and `R8-08` remains excluded.
  Nothing here may be read as precedent for either.
- **No counting, ranking, or frequency.** "Most used", "opened 12 times", "trending" — each requires
  an access record this decision does not authorize. Recency is an ordering over records that exist;
  frequency is a new measurement.
- **No cross-organization or cross-account view.** A pin belongs to one `owner_id` scope, and the
  activity view shows one scope's own records.
- **No calculation.** `W1-09`'s own wording is *"without creating a new calculation"*, and
  `RCA-005`'s first exclusion bars *"any calculation, comparison, aggregation or re-rendering of
  figures on a workspace surface."* Neither capability touches a figure.
- **No new audit action.** Pinning is a navigation convenience, not a governed workspace action;
  `AUDIT_ACTIONS` is unchanged. Recording pins in the audit trail would put a product signal into a
  security record, which `RCA-005` forbids.

### 3. Why recency and not frequency

Frequency is the more useful feature and the more costly one. Counting how often an owner opens an
analysis means retaining an access record per read — a behavioural log, under a purpose
`KHEPRI-DEC-015` §3 does not grant, that grows with use rather than with content. Recency asks only
*"what does this scope hold, and when was each thing last written"*, which the workspace records
already answer. Constitution VII's least-data default decides between them, and this decision takes
the answer that adds no data.

### 4. Consequences if this is not approved

`W1-09` stays unbuilt and M3 ships without pins or a recent-activity view. That is a real cost and a
survivable one: `W1-05`'s Overview, Data and Analyses surfaces are reachable by navigation, so the
capability is convenience rather than access. The alternative — building it under `FR-125`'s audit
events — is the reading `RCA-005` forbids, and is not available.

## Obligations if approved

1. `RCA-005` gains `FR-128` (pins) and `FR-129` (the activity view), as drafted in the accompanying
   specification amendment. Without them `W1-09` still has no requirement to build against.
2. The pin row is a new workspace table under `KHEPRI-DEC-033` §2's discipline, with a migration and
   a cascade from the pinned object's deletion, tested per `FR-127`'s deleted case.
3. `W1-09`'s surfaces state nothing about expiry that `KHEPRI-DEC-033` §5's caution forbids.
4. A test proves no access count, no frequency measure and no telemetry event is written by either
   capability — the guard against this decision being widened by implementation.

## What this decision does not reopen

`KHEPRI-DEC-015` §2's identity matrix, §3's purpose limitation, §4's minimization, §6's deletion
rules and §8's backup invariants all stand unchanged. `KHEPRI-DEC-033`'s content matrix stands
unchanged. This decision adds one row to neither: it adds one new class of its own, and one view that
retains nothing.
