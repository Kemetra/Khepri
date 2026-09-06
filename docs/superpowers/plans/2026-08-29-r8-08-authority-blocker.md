# R8-08 activation telemetry — blocked on approved scope

**Baseline:** `origin/main` at `844d51b`, 2026-08-29.
**Finding:** R8-08 cannot begin implementation. Recorded rather than worked around.

## The blocker

R8-08 is *"Govern and implement content-free product activation telemetry"* (roadmap §R8 completion
table, line 796). Its `Depends on` column is **"approved scope"** — not a merged slice. Three
independent checks agree it is absent:

1. **Roadmap line 796** — the dependency is literally an approval, not an artifact.
2. **Roadmap line 1714** — R8 is `READY_FOR_PLAN`, and the stated reason is *"R8-08 telemetry scope
   remains."* Per §15, a program's status is the status of its next actionable task.
3. **`governance/registry.yaml`** — no `R8-08` row, and no activation-telemetry artifact of any kind.

## Why the two ACTIVE specs do not supply the authority

`RRA-010` and `RCA-002` are both ACTIVE, which is what made R8-08 look startable. Being ACTIVE is not
sufficient: the question is whether the spec's **scope admits the work**.

`RRA-010.md:93` lists under its non-goals:

> Any new data collection, field, **telemetry event**, or persistence.

So `RRA-010` explicitly excludes the thing R8-08 would build. `RCA-002` does not mention telemetry at
all. Neither spec can carry this slice.

This is the "proposals must carry their registry row" pattern that blocked the AI provider work
twice: an ACTIVE neighbour is not authority for work its scope excludes.

## Existing telemetry is not a precedent

`khepri.rra` already has `telemetry.py`, `stage_telemetry.py`, `telemetry_persistence.py`, and
`telemetry_service.py`. These are **pipeline stage** telemetry under the RRA specifications, not
product **activation** telemetry across the invite → auth → org-selected → analysis-started →
admission-reviewed → report-ready → evidence-opened → report-downloaded journey that R8-08 names.
Extending them to carry activation events would be the same unapproved data collection `RRA-010:93`
refuses.

## The rest of R8 is blocked too

| Task | Dependency | State |
|---|---|---|
| R8-08 | approved scope | **Absent** |
| R8-09 | amending or successor identity authority over `KHEPRI-DEC-025` §2 | Absent — this is `R8-03` reopened |
| R8-10 | T1 minimum | T1 has no registry row |
| R8-11 | CAL1, T1, OPS1 staging | CAL1 is `IN_IMPLEMENTATION`; OPS1 deferred |

## What would unblock R8-08

An owner-approved scope for content-free activation telemetry, carrying its own registry row, naming:

- the eight journey events, and that they are content-free;
- where they persist, and under whose retention authority;
- the amendment or successor that lets `RRA-010:93` admit a new telemetry event, or the new
  specification that owns them instead.

Governance work is a separate lane from implementation and does not belong in this branch.

## Disposition

No code written. The worktree and branch exist and are clean. Lane B should either take an
owner-approved governance slice for the scope above, or stand down until one exists.
