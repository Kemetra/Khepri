# #569 and #560 item 1 -- the decision surface's series rows and card status

Date: 2026-09-25. Branch `fix/569-series-value-kind`. One PR: this plan and the RED tests
first, then the implementation.

## Authority

- `RRA-014` is `active` in `governance/registry.yaml`, and its §Scope is
  `src/khepri/rra/semantic_views/` and `tests/`. The #569 fix lands inside that scope, in
  `projection.py`.
- `RCA-008` is `active`, and its §Scope is `src/khepri/rca/workspace/` and the decision surfaces.
  #560 item 1 would land there. This plan finds that item needs an owner reading and does not
  change it (see below).
- No specification, validator or governance file is edited.

## What the golden package shows

These figures come from the real projector over `ReportBundle.of(package())`.

- The bundle carries 19 `value` figures and 14 `rows` figures. Every `rows` figure is a
  series-bucket row count, and it has the same metric as the measure beside it.
- `BranchPerformanceView` projects 8 rows. 4 of them are row counts (`Cairo revenue_by_store 2`).
- `ProductCategoryView` projects 8 rows, and 4 of them are row counts.
- The rendered decision surface prints 16 breakdown `value` cells. 8 of those are row counts.
- `ReportEvidenceView` projects 5 rows, all of them scalar core citations. Its
  `dimension_allowlist` is `(period,)`, so `_admits_dimension` excludes every store, product and
  category series. **No row count is reachable on `ReportEvidenceView` today.** The issue's
  option 1 assumed it was.
- `CitedEvidence` for a series citation states `precision`, `inputs=None` and
  `provenance=None`. It does not state the row count.

## Reading taken for #569 (for owner review)

**Option 1 is taken: a view that publishes a `value` field selects `kind == value` figures.** No
amendment is needed. This is the order of the clauses that support it.

1. **`RRA-014 FR-139` makes today's output the defect.** It says: "Projected typed values ...
   equal the source records; no re-rounding, relabelling outside governed vocabulary, or
   substitution is allowed." A row reads `metric=revenue_by_store, value=2`, but the source record
   for `revenue_by_store` in Cairo states `335.75`. The `2` is a different record, a
   `CitedFigure` of kind `rows`. Printing it in the measure's `value` column puts a count where
   the measure belongs, which is substitution. Relabelling a count as revenue is outside governed
   vocabulary: `rendering/wording.py` qualifies a `rows` figure as "rows counted" wherever it is
   shown.
2. **`RRA-014 FR-138` permits the fix.** It says: "Projection may select, use governed wording,
   and deterministically order existing fields." Choosing the figures whose kind is the published
   column's meaning is selection. It adds no arithmetic, aggregation, ranking or threshold.
3. **`RRA-014 FR-140` is not engaged.** It says: "Every source refusal, caveat, population
   qualifier, evidence value, and governed evidence absence survives projection." A `rows`
   `CitedFigure` is none of those: it is a figure, not a caveat, refusal, qualifier or
   `CitedEvidence` value. Every caveat and evidence record still travels whole on
   `ViewProjection.caveats` and `.evidence`, and a test pins that.
4. **`RRA-014 FR-134` does not fire.** It says: "changing any admitted source, field, metric,
   dimension, filter, evidence requirement, empty rule, or output order creates a new version."
   None of those contract fields changes, and `PUBLISHED_DIGESTS` still matches every definition.
   So the v1 identities stay, and no new version is published.

**Where row counts stay reachable.** They stay on the bundle (`ReportBundle.figures`) and on the
`RRA-006` report surfaces (HTML, PDF and Excel), which print them with the `KIND_ROWS` "rows
counted" qualifier. They are **not** reachable through any semantic view. The issue's premise
that `ReportEvidenceView` carries them is false, and this PR records that rather than adding a
reader.

**Option 2 is not taken.** Option 2 would publish `kind` as a field. That changes
`output_field_order`, which `FR-134` makes a new version. It also moves the `RCA-008`
`FR-160` literal pins. It widens the slice beyond fixing a misstatement.

**The rule is gated on the published field, not the view name.** The selection applies when
`"value" in definition.output_field_order`, the same idiom `_rows` uses for `availability` and
`subject`. So `MetricAvailabilityView` (whose `available` reading counts any carried figure),
`ReportEvidenceView` (`figure`) and `PeriodComparisonView` (`subject`/`baseline`/`delta`) are
untouched. `ExecutiveOverviewView`, `BasketView` and `ConcentrationView` also publish `value`, so
they get the same rule. On the golden package their output is unchanged.

**Edge case, recorded and not changed.** A series cell whose `value` is `None` yields only a
`rows` figure (`bundle._bucket`). After this fix, that bucket projects no row on S-3 or
S-4. Before the fix it projected its row count as the measure. The golden package has no such
cell. Whether an absent bucket measure should surface as a stated absence is a separate
`RRA-014` question.

The Arabic-digit observation in #569 says "no defect claimed", and this PR does not change it.

## #560 item 1 -- blocked on an owner reading, not changed

**Premise checked.** `card._admitted` qualifies each card with `projection.caveats`, the
`ExecutiveOverviewView` projection's own caveats. That is already the pattern `RCA-008 FR-167`
states for breakdowns: "A breakdown figure is qualified only by its own projection's caveats and
population qualifiers and by the outcome that fetched it." The breakdown read model does the
same thing (`BreakdownReading.caveats = projection.caveats`).

**Why no scoping makes a real card `verified`:**

- The golden bundle's only caveat is `StatedCaveat("chart_not_drawn", section="overview")`.
- Every card's figure sits in that same `overview` section.
- The caveat is structural. `bundle._plottable` says: "The overview declares none and keeps no
  chart." So every present overview section carries `chart_not_drawn`, and every card over any
  real bundle carries its own section's caveat.
- `RCA-008 FR-162` selects status from "whether the projection carries caveats". Read plainly, a
  real card is correctly `caveated`.
- `RRA-014 FR-140` bars the projector from dropping the caveat.

The only change that would produce `verified` is deciding that `chart_not_drawn` does not qualify
a scalar card, and excluding it by code in `card.py`. That is a caveat-semantics decision. No
active clause authorizes it, and `definitions.summarize` treats the caveat as a section
qualification. It needs an owner reading of `RCA-008 FR-162`, for example "caveats that qualify
the figure, not the section's chart". It is left open on #560.

## Implementation (commit 2)

- `projection.py`: add a small predicate `_as_published(figures, definition)`. It keeps
  `kind == KIND_VALUE` figures when the definition publishes a `value` field, and otherwise
  returns `figures` unchanged. Apply it in `_projection`. Do not grow `_admitted_figures`.
- Update the module docstring's selection note.

## Tests (commit 1, RED)

`tests/test_issue569_series_value_kind.py` runs over the real projector and the golden bundle. It
holds these checks:

- **Precondition extents:** 19 value figures, 14 row counts, and 4 of each on the store series and
  on the category series.
- **Exact projected rows as literals:** `BranchPerformanceView` 8 → 4, and
  `ProductCategoryView` 8 → 4.
- **FR-140:** caveats and evidence are unchanged.
- **Views without a `value` column keep their extents:** availability 22 and evidence 5.
- **FR-134:** every digest matches.
- **`read_branches` / `read_products`:** exactly the 4 measure rows each.
- **Rendered decision surface:** 8 breakdown value cells in English and in Arabic, not 16.

RED: 6 tests fail on the defect and 4 guard tests pass.

**Mutation checks after GREEN:**

1. Delete the predicate call.
2. Invert the kind test.
3. Gate on a field no view publishes.

Each must turn the tests red.
