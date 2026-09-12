# `D1-06`–`D1-10` — Planning refinement, and what each slice may not decide

**Status: this is not six execution plans.** `D1-05` has one
(`2026-09-12-d1-05-execution-plan.md`) because its dependency is merged and its inputs are
verifiable on `main` today. `D1-06` through `D1-10` get theirs **at their turn**, and this document
records why that is a discipline rather than a shortfall.

---

## Why these are refined and not fully planned

The two execution plans this repository already has were written **just-in-time, consuming what the
prior slice found**. `D1-04`'s opens with "What `D1-03` handed forward, verbatim"; `D1-03`'s opens
with "four scope questions answered from precedent". Neither could have been written a week early:
the precedent they consume did not exist yet.

`D1-04` proved the cost of the alternative inside one session. Its plan shipped saying the
composition root was out of reach — and the review that followed found the decision route absent
from the built image, which made that section wrong before the PR merged. A `D1-08` plan written
today, before `D1-05`, `D1-06` and `D1-07` exist, would be falsified the same way and by the same
mechanism.

So what follows is the **binding** work: the traps each slice must not walk into, the readings it
may not take, and the owner items it must raise rather than resolve. Those are knowable now. RED
step lists for surfaces that do not exist are not.

---

## `D1-06` — The navigable report workspace

**Requirements:** `FR-159`, `FR-161`, `FR-165`. **Blocked by:** `D1-05`.

- **S-8 is refactored, not built.** The existing report page becomes navigable; a slice that builds
  a second report surface has created the two-definitions problem the repository fails closed on.
- Reads the `RRA-006` report bundle and `RCA-005` analysis detail — two authorities, and `FR-165`
  makes the reads independent: one available while the other is not still renders.
- **Watch the access path, not just the values.** `[[a-batching-fix-regresses-the-single-item-caller]]`:
  `#378` fixed a spine and made detail read the whole scope. Value assertions cannot see that.

## `D1-07` — Visible controls, modelled as what they actually are

**Requirements:** `FR-166`, plus `FR-164`. **Blocked by:** `D1-04` (not `D1-06` — parallel-safe).

- **The "global period filter" is not a filter, and this is the whole slice.** No published view
  names `period` in `request_filter_allowlist`; five name no request filter at all. A period is a
  property of the run's package, so **choosing a period is choosing a `source_id`**.
- The only real view filters are `store`, `product`, `category`, on the three views that admit them.
  Workspace is the organization scope, resolved by `resolve_scope` **before any read**.
- A filter bar that passes a period into `ExecutiveOverviewView` gets a **refusal**, because
  `FR-137` refuses an unsupported filter before projection rather than dropping it. Making that
  structurally impossible is the point of the slice.
- `FR-166`: effective filters shown come from the `EffectiveRequest` **on the outcome**, never a
  copy the surface keeps. `FR-169` bars retaining any of it between requests.

## `D1-08` — Presentation without recalculation

**Requirements:** `FR-159`, `FR-168`, §Retention. **Blocked by:** `D1-03`…`D1-07`.

- **Print is in scope. A stored snapshot is excluded** — §Retention ("retain nothing of their own"),
  §Exclusions (no new stored column), and `FR-168` each bar it independently.
- **The export reading is an OWNER ITEM and this slice may not resolve it.** §Exclusions bars "no
  cross-organization access, sharing, or export"; whether the modifier reaches all three nouns or
  only the first is not resolvable from the document. **Raise it; do not decide it** — and
  specifically, do not take the reading that lets the slice ship.

## `D1-09` — Latency behavior, pointed at acquisition

**Requirements:** `FR-168`, §Verification's measurement discipline. **Blocked by:** `D1-08`.

- **The target is acquisition, and `SV1-08` already fixed that.** Ledger §3a: composed request
  4003 µs p50, projection 11.6 µs — one part in 345. Optimizing projection would move nothing.
- **`FR-168` removes the usual instruments**: no cache, pre-aggregation, materialized view,
  sampling, or persisted projection. What remains legitimate is the **number of reads per surface**
  and **coalescing reads within one request**.
- **The line that must be asserted, not reviewed:** coalescing within a request is not a cache;
  keeping a result *between* requests is one, whatever it is called. Assert nothing is retained.

## `D1-10` — Cross-cutting parity and refusal-state evidence

**Requirements:** `FR-171`, re-asserting `FR-163`/`164`/`165`/`167`/`170`. **Blocked by:** all above.

- **This slice does not close its own roadmap row, and that gap is an owner item.** Authorized:
  Arabic/English parity, refusal-state tests, cross-organization isolation, and RTL/mobile *as
  parity evidence*. **Not authorized:** the accessibility-evidence programme and visual regression —
  they remain `U1-03`, `U1-05`, `U1-06` and `U1-07`'s and need their own authority.
- The `FR-170` unreachability assertion must **still be standing** when this slice finishes.

---

## What none of these six slices may do

1. **Bind the Period Comparison source.** `RCA-008` §The open question, precondition 2: the binding
   is a composition-root change in a file `RCA-007` §Scope already governs, and two active
   specifications over one file is the ambiguity this repository fails closed on. A successor
   composition artifact is the precondition and **it is owner-authored**.
2. **Remove the `FR-170` unreachability assertion.** Only the slice that makes the source reachable
   removes it. Not `D1-08`, not `D1-10`.
3. **Schedule `D1-11`.** It is **unauthorized, not unplanned**: `RCA-008` §Retention states
   `KHEPRI-DEC-015` §3's prohibition on repeat-use telemetry "is not amended here and `D1-11` stays
   unauthorized." That is why this set stops at `D1-10`.
4. **Authorize any `U1` work.** Precondition 3 makes `U1`'s programme *not a precondition* for D1,
   which is what unblocks these slices — and equally means they are not authorized here.
5. **Add a `deliberately_unwired` entry** to `test_the_built_image_wires_every_optional_field`. If a
   slice needs a new optional `ShellServices` collaborator, it wires it in `build_shell_services`.
   That test exists because the same defect shipped three times (`deletion`, `pins`, `decisions`).

---

## The M4 consequence, stated rather than buried

`RCA-008` deliberately declined the two-population binding, so **completing `D1-02`…`D1-10` does not
satisfy M4's "compare governed periods."** The successor composition artifact is the precondition,
it is owner-authored, and the alternative is accepting an M4 milestone with that clause unmet. This
is named here so no slice discovers it at acceptance time.
