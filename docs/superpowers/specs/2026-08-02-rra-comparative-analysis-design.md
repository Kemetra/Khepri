# RRA comparative and concentration analysis — design

Date: 2026-08-02

Authority: none. This document designs a specification that does not exist yet. The `RRA` family
is `active` and `RRA-004` is `approved` in `governance/registries/`, and both bound the work below,
but nothing here is approval and nothing here changes a registry.

## Outcome

One new specification, provisionally `RRA-008`, adds four families of deterministic derived facts
to the fact package: period comparison, concentration, growth decomposition, and basket structure.
Each reconciles to the `RRA-004` aggregates it derives from, and each refuses rather than misleads
when its preconditions fail.

## Why this is a specification and not a family

`RRA` excludes "forecasting, generic analysis, customer-authored formulas, and unsupported
metrics", and `RRA-004` repeats the prohibition in stronger terms: "Never fabricate metrics,
forecast, apply customer-defined formulas, or emit generic non-retail analysis." Everything
designed here is deterministic retail measurement computed from admitted inputs, so none of it
touches those prohibitions and neither the family document nor `RRA-004` is amended.

Forecasting and customer-defined metrics were considered and rejected for this slice. Either would
require amending an approved specification and the family's `Excludes` list before any code, and
customer formulas additionally contradict the one-source-of-numbers model, because a customer
formula produces a numerical claim the fact package did not compute and cannot reconcile.

## Dependency surface

`RRA-008` depends on `RRA-004` alone.

`RRA-003` fixes eleven semantics — `transaction_date`, `revenue`, `units`, `transaction_id`,
`product`, `category`, `store`, `channel`, `cost`, `discount`, `returns` — with revenue and units as
core measures. Every analysis below is answerable from that vocabulary, so **no new mapping
semantics are introduced and `RRA-003` is untouched**. `RRA-005` and `RRA-006` consume the new facts
through the existing `FactPackage`, `NarrativeAdapter`, and `ReportBundle` contracts.

## Period comparison

A current window is compared to a prior window of equal length, for period-over-period and
year-over-year.

**Like-for-like truncation.** When the current window is incomplete, both windows truncate to the
same day count and a caveat naming the truncated window appears on every surface, in both
languages. A shop that has uploaded through the fifteenth and asks for month-over-month otherwise
sees revenue "down 48%" when it may be up; comparing day 1–15 against day 1–15 is what a competent
analyst does by hand, and the caveat keeps the truncation visible rather than silent.

Refusing whenever a period is incomplete was considered and rejected: it withholds the comparison
at exactly the moment a beta client most wants one. Reporting untruncated totals with a caveat was
rejected because it puts a misleading percentage on the page and relies on the reader noticing
prose, which is weaker than `RRA-004`'s existing caveat-or-refuse posture.

**Absent history refuses the comparison, not the report.** Year-over-year without prior-year
coverage emits a refusal for that comparison while every other fact is delivered.

**Percentage deltas refuse on a zero or negative base.** `RRA-004` already requires documented
zero, null, sign, and aggregation semantics; a percentage change from zero is not a large number,
it is undefined, and a percentage change from a negative base inverts meaning. The absolute delta
is still emitted in both cases.

Granularity follows `RRA-004`'s existing rule, with the 92-day span deciding day or month buckets.

## Concentration

Ranked cumulative revenue share by product or category — which few items carry the business.

**Concentration is computed over the full distinct-value set, never the truncated bucket set.**
`RRA-004` caps comparisons at 20 buckets with an `other` aggregate plus the `unlabelled` and
`redacted` reserved labels. A cumulative-share curve computed over 20 buckets and an `other`
aggregate is not a concentration curve: it understates concentration when `other` is large and
overstates it when `other` is small, and the error is invisible on the surface. The fact therefore
records `distinct_values` and the count actually ranked, and only the *display* truncates. Where the
full distinct set cannot be computed within admissibility limits, the analysis refuses.

**No fixed ABC classes.** An 80/15/5 split is a reporting convention, not a property of the data,
and inventing thresholds is the metric fabrication `RRA-004` forbids. What is emitted instead is
measured: the ranked cumulative curve, and the revenue share held by the top decile and the top
quartile of ranked values.

## Growth decomposition

A revenue change is split into the part attributable to price and the part attributable to volume,
so that "revenue up 8%" becomes "five points price, three points volume".

The decomposition is two-term and exactly additive:

```
Δrevenue = (ASP_prior × Δunits) + (units_current × ΔASP)
```

where `ASP = revenue / units`. The identity is exact rather than approximate:

```
P₀(Q₁ − Q₀) + Q₁(P₁ − P₀) = P₀Q₁ − P₀Q₀ + Q₁P₁ − Q₁P₀ = P₁Q₁ − P₀Q₀ = ΔR
```

The parts sum to the whole by construction, so the reconciliation `RRA-004` requires cannot drift
and no residual term has to be explained on a report surface. A three-term price/volume/mix model
was rejected for the opposite reason: it requires a residual whose size is an artifact of the
model rather than a fact about the business.

The identity does assign the interaction term to price, which is a choice and not a law. The
specification states it explicitly and pins the formula version, so a later change to the
convention is a governed change with a new version rather than a silent restatement of history.

Decomposition refuses when units are zero in either period, because average selling price is then
undefined.

## Basket structure

Items per transaction, and attach rate as the share of transactions containing a given dimension
value.

**Both require `transaction_id`, which `RRA-003` treats as optional.** When it is absent, both
refuse with a stated reason. Row count is never substituted for transaction count: a dataset at
line-item grain would otherwise report a basket size of exactly one item per transaction, which is
wrong and looks plausible.

Attach rate additionally requires an admissible product or category dimension.

## Cross-cutting requirements

- Every derived fact reconciles to the `RRA-004` aggregate it derives from, and emits a caveat or
  refuses the affected result when reconciliation fails.
- Stable fact and citation identifiers, with input digest, mapping version, formula version,
  dimensions, filters, units, precision, and caveats recorded, as `RRA-004` already requires.
- Reruns with identical input and governed versions are byte-equivalent.
- Arabic and English carry equal facts, caveats, and citations.
- No forecasting, no customer-defined formulas, no generic non-retail analysis.
- **Cohort and repeat-purchase analysis is permanently out of scope.** The mapping vocabulary has
  no customer identifier, deliberately, because `RRA-003` requires likely personal-data columns to
  be detected and excluded from narrative and reporting inputs. The specification states this so it
  reads as a boundary rather than an omission.

## Verification

Golden-dataset tests per analysis, covering: like-for-like truncation and its caveat; refusal on
absent prior-year coverage; zero and negative percentage bases; missing `transaction_id`;
line-item-grain data not being mistaken for transaction grain; decomposition additivity asserted as
an exact equality rather than a tolerance; concentration computed over the full distinct set while
the display truncates; bilingual caveat parity; and deterministic rerun.

## Delivery

The registry entry is `draft` with `depends_on: [RRA-004]`, in family `RRA`. Implementation is four
independently verifiable slices, one per analysis — the specification is one document, the work is
four, and each slice carries its own tests and review.

## Out of scope

Two-dimension breakdowns such as category × store are deferred to a later specification. They
interact badly with the 20-bucket cap, since a naive crossing produces up to 400 buckets, and the
truncation rule that keeps them honest deserves its own design rather than a paragraph here.

Forecasting, customer-defined metrics, new mapping semantics, and any change to `RRA-003` or
`RRA-004` are outside this work.

## What this design does not do

It creates no specification document, no registry entry, no approval package, and no code. `RRA-008`
does not exist until it is written and its entry is added, and it authorizes no implementation until
its registry entry records approval evidence from the named active authority. A design document is
not authority, and neither is a merged pull request.
