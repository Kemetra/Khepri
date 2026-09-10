# `D1-01` — Executive workspace information architecture, narrative order, and the fact/view source map

**Authority:** none of its own. This note is **product scope**, not a governed artifact. It reads
`RRA-014` (active), `RCA-006` (active), `RCA-007` (active), `RRA-011` (active), `RRA-012` (active),
`RCA-005` (active) and `KHEPRI-DEC-015` (active), and decides nothing any of them left open.
**Roadmap:** `D1-01`, first incomplete item on the critical path (§17 item 23). Its `C1`/`SV1`
dependency is met on both halves; §16's `D1` row moved to `READY_FOR_PLAN` at `659b342` (`#439`).
**Raised on:** `main` at `659b342`, after `#437` bound the semantic-view projection to the query
orchestration and made a view over a scoped run return a projection rather than a refusal.
**Consumed by:** the owner-authored specification that governs the D1 product-code files, and then
`D1-02`…`D1-11`. Nothing may be built from this note alone.

---

## 0. Why this is a note and not a specification

The same three grounds `G4-01` §0 records, which hold here unchanged and are not re-argued:
there is no `proposed` state (`ARTIFACT_STATES = {"active", "retired"}`,
`src/khepri_gov/validator.py:15`); a new `specification` row must depend on exactly one family
(`validator.py:302-308`), which would pre-empt the RRA/RCA split the D1 authority has yet to make;
and Article IV governs product code, not scope definitions.

One ground is specific to `D1`. **No existing active specification can host this scope.**
`RRA-014` §Scope admits `src/khepri/rra/semantic_views/` and puts "runtime routes, templates, shell
assets, workspace persistence" outside it. `RCA-006` adds "no route, runtime wiring, template,
shell asset, public API, migration, cache, background job, renderer, or existing workspace file is
governed." `RCA-007` is the composition boundary and excludes routes and HTTP responses by
`FR-158`, asserted in test. **D1 is entirely made of the things all three exclude.** Its authority
is therefore new, and owner-authored.

---

## 1. The one question `D1` exists to answer

`SV1` made governed facts *readable* through eight versioned projections. It did not decide what a
customer sees first, in what order, or which projection answers which question. Every view is a
selection over one run's facts; none of them is a page.

**`D1`'s question is therefore: what is the smallest set of surfaces that turns eight projections
into one decision, without deriving a single number outside them.** §16's `D1` row and the M4 exit
gate both state the constraint the same way — no calculation outside RRA facts and SV1 views — so
this note's job is to say where each figure on each surface comes from, precisely enough that a
later slice cannot quietly compute one.

Everything below answers that and nothing else.

---

## 2. The nine surfaces, and the three that are not `SV1`'s

§7's `D1` program lists nine product surfaces. **Six are served by semantic views. Three are not,
and this is the note's first load-bearing finding**, because `D1-02` is worded "Build executive
overview read model **from SV1 only**" and a reader can carry "only" from the figures to the page.

| # | Surface | Served by | `SV1`? |
|---|---|---|---|
| **S-1** | Executive Overview | `ExecutiveOverviewView` | Yes |
| **S-2** | Period Comparison | `PeriodComparisonView` | Yes — **but see §6, F-1** |
| **S-3** | Branch Performance | `BranchPerformanceView` | Yes |
| **S-4** | Product/Category Performance | `ProductCategoryView` | Yes |
| **S-5** | Basket and Concentration | `BasketView` + `ConcentrationView` | Yes — two views, one surface |
| **S-6** | Exceptions, Caveats, and Refusals | `MetricAvailabilityView` + every projection's own `caveats` | Yes |
| **S-7** | Recent Analyses and Comparisons | `W1` workspace records and pins | **No** |
| **S-8** | Navigable Report Workspace | `RRA-006` report bundle, `W1` analysis detail | **No** |
| **S-9** | Metric Detail and Evidence Drawer | `RRA-011` catalog + `RRA-012` drawer + `ReportEvidenceView` | **Partly** |

**"From SV1 only" is a rule about figures, not about pages.** No published view projects a list of
runs, so S-7 cannot be an `SV1` read at any version — `ScopedSourceReader.get_analysis_run` reads
*one* run by id, and a view is a projection over a bundle, not over a workspace. S-8 is an existing
surface `D1-06` refactors rather than builds. S-9's *definition* half — label, formula, bilingual
wording — is `RRA-011`'s catalog, which `T1-05` shipped; only its *figure* half is a view.

**Read the rule as "no figure on any D1 surface is derived anywhere but an SV1 projection", and
every surface above is admissible.** Read it as "every D1 surface is an SV1 read", and S-7 is
unbuildable and S-9 loses its definitions. The D1 specification should say which, in one sentence.

---

## 3. Narrative order

One rule fixes it, in the shape `G3-04` and the `SV1` allocation plan both used:

> **A claim may be shown only after the reader can see whether it is allowed to be made.**

That puts availability and limitation *before* breadth, not after it — the inverse of the usual
dashboard, and the whole of Khepri's premise. The order is:

1. **S-1 Executive Overview** — the ten core metrics for one run. First because it is the smallest
   complete answer, and because `MetricAvailabilityView` can qualify it without another read.
2. **S-6 Exceptions, Caveats, and Refusals** — second, not last. `FR-140` keeps a governed absence
   intact through projection, and a reader who scrolls past the overview without meeting its
   caveats has already formed the conclusion the caveat exists to qualify.
3. **S-2 Period Comparison** — change, once level is established and qualified.
4. **S-3 / S-4 / S-5** — breakdowns, in that order: store, then product and category, then basket
   and concentration. Narrowest governed dimension outward.
5. **S-9 Evidence drawer** — reachable from every figure on all of the above, never a page of its
   own. `RRA-012`'s component layer and `U1-04`'s drawer already place it beside an evidence row.
6. **S-7 / S-8** — return paths, not analysis. They belong at the workspace level, above this
   narrative rather than inside it.

**Build order is not this order.** S-6 is second in the narrative and cannot be built second: it
reads every other surface's caveats, so it lands after the surfaces that produce them. The one
ordering constraint on *building* is that S-1 precedes all of S-2…S-5, because it is the only
surface whose read path has been exercised end to end (`SV1-07`'s composition property, re-run on
the shipping root at `#437`).

---

## 4. The exact fact/view source map

Every figure on every D1 surface, and the exact projection field it comes from. Resolved from the
published registry at `659b342` rather than transcribed — `FR-135` forbids retyping a metric code,
and this table would be a second truth if it named metrics the registry does not.

| Surface | View `view_id` | `view_version` | Source shape | Metrics projected | Dimension | Output fields, in published order | Empty rule |
|---|---|---|---|---|---|---|---|
| S-1 | `ExecutiveOverviewView` | `sv1.executive_overview.v1` | single | the 10 core: `revenue`, `cost`, `gross_profit`, `gross_margin`, `units`, `transactions`, `returns`, `discount`, `average_order_value`, `average_selling_price` | `period` | `metric`, `value`, `population`, `versions` | `stated_absence` |
| S-2 | `PeriodComparisonView` | `sv1.period_comparison.v1` | **two** | the 10 core + `revenue_delta_absolute`, `revenue_delta_percent`, `growth_revenue_change`, `growth_price_effect`, `growth_volume_effect` | `period` | `metric`, `subject`, `baseline`, `delta`, `versions` | `stated_absence` |
| S-3 | `BranchPerformanceView` | `sv1.branch_performance.v1` | single | `revenue_by_store`, `units_by_store` | `store` | `store`, `metric`, `value`, `population` | `stated_no_rows` |
| S-4 | `ProductCategoryView` | `sv1.product_category.v1` | single | `revenue_by_product`, `revenue_by_category`, `units_by_product`, `units_by_category` | `product`, `category` | `dimension`, `member`, `metric`, `value`, `population` | `stated_no_rows` |
| S-5a | `BasketView` | `sv1.basket.v1` | single | `basket_attach_rate`, `basket_items_per_transaction` | `period` | `metric`, `value`, `population`, `versions` | `stated_absence` |
| S-5b | `ConcentrationView` | `sv1.concentration.v1` | single | `concentration_curve`, `concentration_distinct_values`, `concentration_ranked_values`, `concentration_top_decile_share`, `concentration_top_quartile_share` | `product`, `category` | `dimension`, `metric`, `value`, `population` | `stated_absence` |
| S-6 | `MetricAvailabilityView` | `sv1.metric_availability.v1` | either | all 22 published metrics | all five | `metric`, `availability`, `reason`, `versions` | `stated_absence` |
| S-9 | `ReportEvidenceView` | `sv1.report_evidence.v1` | either | the 10 core | `period` | `figure`, `evidence`, `provenance`, `absence` | `stated_absence` |

**The two empty rules are not interchangeable and the surface must render them differently.**
`stated_no_rows` means the admitted request matched nothing — S-3 with a store filter naming a
store with no sales. `stated_absence` means the governed source published no value at all — a
refused or unavailable measure. `contracts.py` states why they are distinct: *"nothing matched what
you asked" is not "we could not compute this"*. A surface that renders both as an empty table
tells the customer the wrong thing about their data.

**Every view's `required_evidence` is `()` at v1.** Not an oversight to correct in D1: `FR-141`
makes a required-but-absent evidence code a refusal cause, and the v1 registry requires none, so no
D1 surface may present evidence *absence* as a view refusal. Absences arrive instead as
`ViewProjection.evidence_absences`, which is data on an admitted projection.

**The read a D1 read model actually performs**, for every row above:

```text
SemanticQueryActions.request(SemanticQueryRequest(
    actor=SemanticQueryActor(account_id),
    organization_id=...,
    view=SemanticViewRequest(view_id, view_version, metrics, dimensions, filters),
    source_ids=(run_id, ...),
)) -> ViewOutcome(kind = admitted | refused | unavailable)
```

`view_version` is named exactly on every call. `FR-143` admits no `latest` alias and no silent
upgrade, so **the D1 read model pins the eight versions in the table above** and a registry
republication is a D1 change, not a transparent one.

---

## 5. The metric card, line by line

§9 lists nine things every customer-visible KPI card must expose. **No single view supplies them,
and this is the note's second finding** — a card is three projections plus the catalog.

| §9 card line | Source | Read |
|---|---|---|
| Metric label | `RRA-011` catalog, bilingual | not a view |
| Value and unit/currency | `value` field | S-1 projection |
| Comparison only when compatible | `subject`, `baseline`, `delta` | S-2 projection, **absent when incompatible** |
| Status: verified / caveated / refused / unavailable | `availability` + `reason`, and `ViewOutcome.kind` | S-6 projection + the outcome itself |
| Population | `population` field | S-1 projection |
| Formula/contract version | `versions` mapping | S-1 projection |
| Visible filters and period | `EffectiveRequest` on the outcome | the request, not a view field |
| Evidence action | `figure`, `evidence`, `provenance`, `absence` | S-9 projection |
| Caveat/refusal count | `ViewProjection.caveats` | S-1 projection |

**The four statuses come from two places and the mapping must be stated, not inferred.**
`ViewOutcome.kind` gives *refused* and *unavailable*; `MetricAvailabilityView` gives `available` /
`partial` / `unavailable` from `definitions`; and *caveated* is an admitted projection whose
`caveats` is non-empty. Selecting among four presentation states from those inputs is presentation,
not arithmetic — but a slice that instead *counts* or *scores* them has crossed `FR-138`.

**"Comparison only when compatible" is served by absence, not by a flag.** S-2 refuses an
incompatible pair before projecting (`FR-137`), so the card has no comparison to show. The card
must render the missing comparison as the governed refusal it is, with `ViewRefusal.wording` in the
page language — `FR-141` requires bilingual wording from governed vocabulary, and inventing an
English "not comparable" string on the surface would bypass it.

---

## 6. Three constraints the published views impose on the IA

These are findings against the shipping code, each verified at `659b342` rather than reasoned from
the specifications.

### F-1. `PeriodComparisonView` cannot be reached through the shipping composition root

`PeriodComparisonView.accepted_source_shape` is `two_population_bundle`, which `contracts.py`
defines as `RRA-006` §Two-population bundle's `CrossVersionBundle`. **The adapter `RCA-007` shipped
builds only single-population bundles.** `semantic_view_adapter._rebuilt_bundle` ends
`return ReportBundle.of(package)`, once per run, and passing two `source_ids` yields two
single-population bundles rather than one cross-version bundle. The shape predicate reads
`bundle_version`: `rra006.bundle.v8` carries no `crossversion` marker, so
`_shape_of` answers `single_population_bundle` and `FR-136` refuses the view.

The only `assemble_crossversion` caller in the runtime is `comparison_assembly.py`, which serves
the `C1` comparison surface and is not bound to the semantic-view port.

**So S-2 is specified, published, and unreachable.** This is not a defect in `SV1` or `RCA-007` —
neither admits the composition that would close it, exactly as `RCA-006` admitted no composition
root until `RCA-007` existed. **It is a scope input for the D1 authority**, which must decide one
of three things, and this note recommends the first:

1. **Admit a cross-version binding in the D1 authority**, so a comparison run's `CrossVersionBundle`
   reaches the port. Smallest, and it reuses `comparison_assembly.py`'s existing assembly.
2. **Scope S-2 out of the first D1 milestone**, shipping S-1 and S-3…S-6 and stating the gap.
3. **Amend `RCA-007`.** Largest, and it reopens a boundary the owner has just ruled on.

`SV1` is the precedent for how to hold this open honestly in the meantime: an absence marker that
fails the day the binding ships. A D1 slice that instead quietly renders an empty Compare tab has
hidden the gap.

### F-2. No view accepts a period filter, so the global period control is a run selector

`D1-07` is "visible global period/workspace/dimension filters with no hidden state". Against the
published registry:

- **Period:** no view names `period` in `request_filter_allowlist`. Five views name **no** request
  filter at all. A period is a property of the run's package, so **choosing a period is choosing a
  `source_id`** — a run selector above the surfaces, not a filter passed into one.
- **Workspace:** `organization_id` on the request, resolved by `resolve_scope` before any read
  (`FR-145`). Not a filter either.
- **Dimension:** the only real view filters. `BranchPerformanceView` accepts `store`;
  `ProductCategoryView` and `ConcentrationView` accept `product` and `category`. **Nothing else
  accepts anything.**

This matters because `FR-137` refuses an unsupported filter *before projection* rather than
dropping it. A D1-07 filter bar that passes a period parameter into `ExecutiveOverviewView` does
not get a period-filtered overview; **it gets a refusal**. The control must be modelled as three
different things wearing one row of the UI, and "no hidden state" is satisfied by
`EffectiveRequest`, which states requested and definition-fixed filters back.

### F-3. One surface, two views is the normal case, and the reads are independent

S-5 is two views; S-6 reads a seventh alongside whatever surface it qualifies; a metric card is
three. Each is a separate `SemanticQueryActions.request` call, each independently authorized, and
**each can independently answer `unavailable`**. A surface must therefore render partial success —
`BasketView` admitted while `ConcentrationView` is unavailable — rather than failing the page.
`FR-146` makes every miss content-free and identical, so the surface may say only that this part is
unavailable, never why.

---

## 7. What `D1-01` must not decide, and who decides it

| Question | Whose | Why not here |
|---|---|---|
| Which package paths D1 code may touch, and its exclusions | The D1 authority, owner-authored | Article IV; every existing spec excludes these files (§0) |
| Whether the cross-version binding of F-1 is admitted, and where it lives | The D1 authority | It is a composition-root question, the kind `RCA-007` exists to answer |
| The read model's types, module layout, and route shapes | `D1-02`, under that authority | `RRA-014` declined to fix even its own field types outside `SV1-02` |
| Chart grammar, navigation, accessibility evidence, visual regression | `U1-03`, `U1-05`, `U1-06`, `U1-07` | No active specification governs those files; `U1` is `BLOCKED` |
| Whether `RRA-012` components may reach a journey page | Owner, against the `RRA-010` journey-adoption filing | Recommends no amendment; **not yet answered**, and no slice may assume option A |
| Any caching, pre-aggregation, materialized view, or sampling | Nobody yet | `FR-144` bars all four from this path; `D1-09` is a governed change |
| `D1-11` decision-use telemetry | Nobody yet | `KHEPRI-DEC-015` §3 unamended; `W1-11`, `R8-08` and `T1-07` all still wait |

**One obligation this note hands forward.** `SV1-08`'s ledger §3a measures the composed request at
**4003 µs p50, of which projection is 11.6 µs — about one part in 345**, putting ~2.7 ms in the
package read, the rebuild and `ReportBundle.of`'s derivation. **`D1-09` must not optimize the
projection or the registry**, and `FR-144` makes the obvious remedy a governed change rather than a
local one. A D1 surface issuing three view reads per card (§5) multiplies that source acquisition,
not the projection — so the read model should acquire a run's bundle once per surface if the D1
authority admits it, and that is an authority question rather than an implementation one.

---

## 8. What this note does not touch

- **`D1-02` through `D1-11`.** All eleven sit behind the D1 authority.
- **The `RRA-010` journey-adoption reading.** Open, the owner's, and `U1`'s blocker.
- **The `KHEPRI-DEC-015` amendment** that `R8-08`, `W1-11` and `T1-07` share.
- **Issues `#429`, `#431`, `#432`, `#434`**, split out of `#438`'s review round for their own PRs.
- **The `M4` exit gate.** It is measured against a deployed image, as `M2` and `M3` were, and
  nothing here is an acceptance record.

## 9. Three things for the owner

1. **`D1-02`'s "from SV1 only" needs one sentence of reading** (§2). Three of the nine surfaces are
   not `SV1` reads, and one of them — Recent Analyses — cannot be at any view version, because no
   projection ranges over runs. The recommended reading is *no figure is derived outside an SV1
   projection*, which admits all nine.
2. **`PeriodComparisonView` is published and unreachable** (§6, F-1). The Compare surface is the
   second-largest thing `D1` promises and its view refuses on the shipping root today. Three
   options are named; the recommendation is to admit the cross-version binding in the D1 authority,
   reusing `comparison_assembly.py`. **This note decides none of them.**
3. **`D1-07`'s "global period filter" is not a filter** (§6, F-2). No published view accepts one,
   and `FR-137` refuses rather than ignores an unsupported parameter. The D1 authority should name
   the period control as a source selector so a later slice does not build a filter bar that
   refuses every request it makes.
