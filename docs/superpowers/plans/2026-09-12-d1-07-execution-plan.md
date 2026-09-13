# `D1-07` — Visible controls, modelled as what they actually are

**Specification:** active `RCA-008`. **Requirements:** `FR-166`, plus `FR-164` for the refusal
path, `FR-169` for retention, `FR-171` for parity. **Blocked by:** `D1-04` (merged, `a65df40`).

**Parallel-safe with `D1-06`.** The refinement document
(`2026-09-12-d1-06-10-planning-refinement.md`) states `D1-07` is "**Blocked by:** `D1-04` (not
`D1-06` — parallel-safe)", and `#452` recorded that `D1-06` has no deliverable. Nothing in this
slice reads or edits the report workspace, so the two do not meet.

---

## 1. What `D1-02`…`D1-05` already built, verbatim

This slice is unusually small because four predecessors built its plumbing while naming it as
this slice's subject. Confirmed on `origin/main` at `9f570bc`:

- **`BreakdownRequest.filters`** exists, defaults to `()`, and `_read_breakdown` passes it to
  `DecisionRead.filters` **unnarrowed**. `breakdowns.py`'s docstring states the rule this slice
  must not break: "A reader that filtered the filters would hold a second copy of the allowlist
  and would drop exactly what the requirement says must refuse."
- **`decision_tail(organization_id, source_id)`** already spells the run as a path segment,
  with `FR-166`'s reason recorded: "the period is a **source selector** — choosing a completed
  run — and not a view filter".
- **`_effective_filters`** already reads `reading.effective` — the `EffectiveRequest` on the
  outcome — and renders requested *and* definition-fixed filters. `FR-166`'s "every effective
  filter is visible in the request and the result" is half-satisfied there already.
- **`read_surface`** constructs `BreakdownRequest` with three arguments, so the filter channel
  is built and **unfed**. Feeding it is this slice's work.
- **`CardsRequest` has no `filters` and must not grow one.** `read_cards` reads
  `ExecutiveOverviewView` and `MetricAvailabilityView`; both publish
  `request_filter_allowlist=()`. A filter field there would be a field whose only possible use
  is to earn a refusal.

## 2. The whole of the slice, stated once

`D1-01`'s F-2, which `RCA-008` `FR-166` made a requirement:

| Control | What it actually is |
|---|---|
| Period | A **source selector** — choosing a completed run, i.e. a `source_id` |
| Workspace | The organization scope, resolved by `resolve_scope` **before any read** |
| `store`, `product`, `category` | The only real view filters, on the three views that admit them |

Verified against `src/khepri/rra/semantic_views/registry.py` at `9f570bc`:

| View | `request_filter_allowlist` |
|---|---|
| `ExecutiveOverviewView` | `()` |
| `PeriodComparisonView` | `()` |
| `BranchPerformanceView` | `(store,)` |
| `ProductCategoryView` | `(product, category)` |
| `BasketView` | `()` |
| `ConcentrationView` | `(product, category)` |
| `ReportEvidenceView` | `()` |
| `MetricAvailabilityView` | `()` |

Five views name no request filter. **No view names `period`.**

## 3. The three readings this slice takes, and why

**3a. An unsupported filter is passed through and refused, never dropped.** `FR-137` refuses
before projection; `FR-166` says a parameter outside the allowlist "does not get it ignored; it
gets a refusal". So the inbound query string reaches the seam verbatim. The literal allowlist in
`controls.py` decides what the surface **offers** — which controls render — and never what it
**sends**. Intersecting inbound parameters with the allowlist would be the silent discard the
requirement exists to forbid, and would hold a second copy of the allowlist besides.

**3b. A dimension control is a filter control, not a `dimensions=` parameter.**
`dimension_allowlist` and `request_filter_allowlist` are different fields;
`ExecutiveOverviewView` admits the `period` *dimension* and zero filters. `seam.py` deliberately
sends no `metrics` and no `dimensions` — "an empty `metrics` or `dimensions` asks for the
definition's own published selection". A control that added a `dimensions` field would
contradict that published-selection contract. The supported dimension controls are therefore
`store`, `product` and `category` — the members of the three real allowlists.

**3c. `resolve_scope` before any read.** The decision route today compares the session's active
organization with the address and passes `organization_id` to the seam. A source list is an
`RCA-005` record read keyed on the opaque `owner_id`, so it goes through
`services.isolation.resolve_scope(account_id, organization_id)` — the existing `RCA-001` bridge
`_workspace_reads` already uses. No second scope path is introduced.

## 4. Filters travel in the query string, and the language switch must carry them

`FR-169` bars "no retained preference, layout, or filter state", so applied filters live in the
address and nowhere else. The shell's language control renders
`{{ prefix }}/{{ alternate }}{{ surface_path }}`, and `surface_path` is `decision_tail(...)`,
which carries no query string. **Left alone, switching EN↔AR drops every applied filter** — the
visible-state requirement failing on the most obvious user action.

`decision_tail` therefore grows an optional filter suffix, built from the same selection the
controls render, and the language-switch test is the one that would catch a regression.

## 5. What this slice may not do

Binding, from the refinement document and `RCA-008` §Exclusions:

1. **No `PeriodComparisonView` source selection.** `FR-170`'s unreachability assertion stays
   standing; only the slice that makes the source reachable removes it.
2. **No new `ShellServices` field.** `records` and `isolation` are already wired in
   `build_shell_services`; no `deliberately_unwired` entry is added.
3. **No recent-analysis list.** The source selector re-addresses *this* surface. A list of
   analyses with their own links is the existing Analyses surface, and `#452` bars duplicating it.
4. No new formula, metric derivation, view version, cache, migration, dependency or CI change;
   no telemetry; no governance edit.

## 6. RED steps

1. `test_d107_controls` — the literal per-view allowlist equals the registry's, derived by
   looping `DECISION_VIEWS` and asserting **extent and non-emptiness**, not a hand-named sample.
   A sample leaves view #4 open when someone widens an allowlist.
2. A supported filter on a view that admits it reaches the seam verbatim and is visible in the
   rendered effective filters.
3. **An unsupported parameter earns a governed refusal**, asserted on the response — not an
   unfiltered overview, and not a dropped parameter.
4. The source selector offers completed runs for the resolved scope and re-addresses this
   surface; `PeriodComparisonView` is not among them.
5. Organization isolation with filters present: org A's address under org B's session returns
   the one uniform unavailable surface.
6. Language switch preserves applied filters, and both languages carry equivalent control copy
   (`FR-171`).
7. Two successive requests with different filters retain nothing between them (`FR-169`).

## 7. Acceptance

No surface sends a parameter a view's allowlist does not name **because it never offers one**;
an inbound unsupported parameter is refused rather than dropped; a period is carried as a
`source_id` and never as a filter; the effective filters shown come from the outcome; nothing is
persisted between requests; applied state survives navigation and the language switch.
