# `D1-08` — Presentation without recalculation

**Requirements:** `FR-159`, `FR-168`, `RCA-008` §Retention.
**Blocked by:** `D1-03`…`D1-07` — all merged (`D1-07` at `79f2d54`, `2026-09-13`).
**Authority:** active `RCA-008`. This plan authorizes no governed-artifact edit.

---

## What this slice ships

**Print, and only print.** The decision workspace becomes printable: the surfaces
`D1-03`…`D1-07` built render to paper without the shell chrome, without re-deriving a
single figure, and without remembering anything about how they were printed.

| Part | Status | Why |
|---|---|---|
| Print | **In scope** | The roadmap row names it; no exclusion reaches it |
| Stored snapshot | **Excluded** | §Retention, §Exclusions and `FR-168` each bar it independently |
| Export | **Refused, and raised** | See below — an open reading, not a ruling |

## The export reading — raised, not decided

`RCA-008`:158 bars "no cross-organization access, sharing, or export". Whether
"cross-organization" modifies `export` or the bar reaches export outright **is not
resolvable from the document**, and this slice does not resolve it.

This plan takes the restrictive reading for one stated reason and no other: the
`D1-06`–`D1-10` refinement directs that absent a ruling, the reading that does **not**
let the slice ship is the one to take. That is a default, not a finding.

**Explicitly not claimed:** that other exclusions (`no public or embedded API`,
`no persistence schema change`) independently bar export. They do not — print is
itself a file-producing path on an authenticated shell route, so an authenticated
export route would not trip them either. The ambiguity is live and stays open.

**Not filed in `RCA-008.md`.** Recording even a restrictive reading into §Exclusions
would author owner authority into a governed artifact. Line 158 is untouched. The item
is raised here and in the PR body; it remains the owner's.

---

## The four constraints this slice is most likely to violate

1. **`FR-159` — print may not derive.** A print layout that re-groups, re-totals or
   re-orders figures for the page is a derivation outside a semantic-view projection.
   Print consumes the *same read model* the screen surface consumes, reshaped only.
   RED test: a print render and a screen render of one run carry identical figures.

2. **§Retention — no remembered print settings.** Orientation, paper size, which
   sections were included: all are "layout state of their own". Barred. Print takes
   what it needs per request and retains nothing. RED test: two successive print
   requests are indistinguishable in stored state.

3. **Prohibition #5 — wire it, do not exempt it.** If print needs a new optional
   `ShellServices` collaborator it is wired in `build_shell_services`. A
   `deliberately_unwired` entry is forbidden: `deletion`, `pins` and `decisions` each
   shipped that defect. RED test asserts the **deployed** route table, not a
   hand-built `ShellServices`.

4. **`FR-170` — the unreachability assertion must still stand.** Verified at the end
   of the slice, not merely left untouched:
   `tests/test_d103_metric_card.py::test_the_period_comparison_source_is_still_unreachable`.

## What this slice may not do

Binding, from the refinement's "What none of these slices may do": no Period
Comparison source binding; no removal of the `FR-170` assertion; no `D1-11`; no `U1`
work; no `deliberately_unwired` entry.

## Verification

`uv run khepri-gov validate`, `uv run ruff check .`, full `uv run pytest`, and the
CodeScene PR gate. RED before GREEN, one PR for the slice.

## Merge authority

Not delegated. The `2026-09-13` "I delegate to you" predates this PR's existence, and
delegations in this repository are per-PR and per-session. The owner's word is asked
on the PR itself once the gates are green.
