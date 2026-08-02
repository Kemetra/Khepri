# Multi-section report surfaces and charts — design

Date: 2026-08-02

Authority: none. This document designs two amendments — one to `KHEPRI-DEC-005` and one to
`RRA-004` — neither of which has been proposed. `RRA-006` and `RRA-008` are `approved` in
`governance/registries/` and both bound the work below, but nothing here is approval and nothing
here changes a registry.

**A registry/prose drift was found while checking this and is recorded rather than fixed.** Both
`governance/specifications/RRA-004.md` and `governance/specifications/RRA-008.md` end with the line
"This specification is draft and does not authorize product implementation," while
`governance/registries/specifications.yaml` records both as `state: approved` with approval
evidence (`APP-002`, `APP-006`). `AGENTS.md` settles which one governs — the registry is
authoritative for state and approval evidence, and approval is never inferred from prose — so
implementation is authorized and the trailing sentences are stale. `uv run khepri-gov validate`
passes regardless, because it does not read that prose. Correcting it touches two governed
documents and therefore needs its own approval; it is not folded into this work.

## Outcome

One report bundle presents its figures as an ordered set of governed **sections**, each carrying an
accessible table and a chart, across all three surfaces. The web report becomes a single document of
page-like sections with navigation, the PDF paginates one section per page, and the workbook carries
one worksheet per section. The four `RRA-008` analysis families supply four of those sections.

## What is already settled elsewhere

This design deliberately covers only what is new. It does not restate:

- The semantics of the four analysis families. `RRA-008` is approved, and
  `2026-08-02-rra-comparative-analysis-design.md` designs them in full — truncation rules, refusal
  preconditions, the exact-additivity requirement, the full-distinct-set rule for concentration.
  What neither settles is whether the fact package *carries* what those rules need; two of the four
  families turn out to need an aggregate that does not exist, which the next section takes up.
- The reconciliation posture. `bundle.reconcile` already refuses a surface that presents anything
  the bundle did not supply, compares figures by rendered **text** rather than value, and requires
  equal figure coverage across languages.
- The one-template rule. `KHEPRI-DEC-005` consolidates bilingual rendering into one Jinja2 template
  so Arabic and English parity has one place to be correct; `report.pdf.html.j2` extends
  `report.html.j2` and fills two blocks.

## Why `RRA-006` is not amended

The section structure was checked against `RRA-006`'s requirements clause by clause and contradicts
none of it. `RRA-006` requires "a navigable web report", and the template already carries a `<nav>`
and five `<section>` elements; more sections is more of what the requirement asks for, not a
departure from it. It requires a "structured Excel workbook with accessible tables, units, formats,
source/citation sheets", and the workbook is already multi-sheet. Charts are named in the
requirements verbatim. The derived facts the new sections carry are authorized by `RRA-008`.

An amendment was drafted for this and then removed. It would have placed a human approval gate on
the critical path in exchange for permission the specification already grants, and manufacturing
approval work is its own kind of governance failure.

## Two of the four families cannot be derived from the fact package as it stands

This is the largest finding in this design, and it is a governance finding rather than a coding one.
`RRA-008` states requirements the current `RRA-004` package cannot supply, and `RRA-008` excludes
itself from fixing that.

### Concentration has no full set to rank

`RRA-008` requires concentration "over the full admissible distinct-value set, never over the
truncated display buckets," including the cumulative share curve and the top-decile and top-quartile
shares. The only dimension aggregate the package carries is `Comparison`, and `build_comparison`
keeps `MAX_COMPARISON_BUCKETS = 20` ranked buckets plus one aggregated `other`. `distinct_values` and
`truncated_values` are **counts**; the omitted values and their revenues are gone by construction.

A cumulative curve over 57 values, or the share held by their top decile, is therefore not
computable from `Comparison` — not "harder to compute", not computable. Ranking the 20 surviving
buckets and labelling the result a full-set statistic would publish a display artifact as a governed
figure, which is the precise failure `RRA-008`'s wording exists to forbid.

### Attach rate has no transaction membership

`RRA-008` requires attach rate as "the share of transactions containing a given admissible dimension
value," and requires that row count never substitute for transaction count. `FactPackage` carries
totals, series, and dimension comparisons. It carries no transaction identifiers and no
transaction-to-dimension membership, and `Bucket` records `rows`, not distinct transactions. The
number of distinct transactions containing a given product is unrecoverable from these aggregates —
a product appearing in 40 rows may sit in 40 transactions or in one.

Items per transaction is a different matter and *is* computable today: `METRIC_UNITS` and
`METRIC_TRANSACTIONS` are both governed facts in the package, and their quotient is the governed
measure. So the basket family splits — one metric available now, one gated.

### Why `RRA-008` cannot authorize the fix

The natural remedy is to have fact-package construction retain the full-set concentration aggregate
and the per-value transaction counts, where every value is still in hand. `RRA-008` forecloses that
under its own authority. Its exclusions name "any change to the profiling, admissibility, or
fact-package specifications this one builds on," and `RRA-004`'s stable contract states that
`FactPackage` "is immutable after publication and is the only numerical source" for every surface.
Adding a required aggregate is a change to the `RRA-004` specification.

So the fix is an `RRA-004` amendment, approved by the named active authority, and it is the **second
approval gate in this work** — independent of the `KHEPRI-DEC-005` one and on the critical path for
two of the four families rather than for the workbook.

### The aggregate the amendment must authorize

Two additions, both deliberately label-free where they can be, and both computed at construction
where the full set is still present:

```python
@dataclass(frozen=True, slots=True)
class ConcentrationCurve:
    """Ranked revenue shares over the full distinct set, before truncation."""

    dimension: str
    distinct_values: int
    ranked_values: int
    cumulative_shares: tuple[Decimal, ...]   # ranked descending, monotonic to 1


@dataclass(frozen=True, slots=True)
class TransactionMembership:
    """Distinct transactions per displayed value, and the full-set denominator."""

    dimension: str
    total_transactions: int
    per_bucket: tuple[int, ...]              # positionally aligned to Comparison.buckets
```

`cumulative_shares` carries no value labels at all — a curve of shares cannot leak a customer value,
so the aggregate that must span the full untruncated set is the one that carries the least. That is
a property worth keeping rather than an accident: the full set is exactly where redaction and label
sanitizing would otherwise have to be re-proven.

`TransactionMembership.per_bucket` is positionally aligned to the buckets the comparison already
publishes, so attach rate is emitted only for values the surface displays, while the denominator is
the full-set distinct transaction count. That keeps the numerator inside the already-reconciled
display set and the denominator governed, without carrying a per-value map of the whole long tail.

Adding either changes the package's document shape and therefore its digest, so `PACKAGE_VERSION`
becomes `rra004.package.v2`. `RRA-004`'s own contract requires that — "a new input, mapping, formula,
or correction creates a new version" — and `reconciles()` must hold for the new aggregates on the
same terms as the existing ones.

### What proceeds while that gate is pending

Unblocked: the section model, period comparison, growth decomposition, items per transaction, the
chart work, and the web and PDF surfaces. Gated on the `RRA-004` amendment: concentration entirely,
and attach rate within basket structure. Gated on the `KHEPRI-DEC-005` amendment: native workbook
charts only.

Until the amendment records approval, concentration's section is `SECTION_REFUSED` carrying
`aggregate_unavailable` and attach rate is refused with the same reason. That is a governed refusal
of the kind `RRA-008` already requires, not a silent omission — and it is the honest state of the
system, since the aggregate genuinely is not there.

## Sections

### A section is data, not layout

`RRA-008` states that the fact package carries the derived facts. A section is therefore a grouping
of `CitedFigure`s by the analysis family that produced them, and the renderers read that grouping
rather than inventing one. Five governed sections, in governed order:

```
SECTION_OVERVIEW       existing RRA-004 headline figures
SECTION_COMPARISON     RRA-008 period comparison
SECTION_CONCENTRATION  RRA-008 concentration
SECTION_GROWTH         RRA-008 growth decomposition
SECTION_BASKET         RRA-008 basket structure
```

Order is governed data. A renderer permitted to choose the order would let the PDF and the workbook
disagree about what a reader sees first, and both would still reconcile.

```python
@dataclass(frozen=True, slots=True)
class Section:
    section_id: str
    state: str                  # SECTION_PRESENT | SECTION_REFUSED
    reason: str | None          # governed reason, only when refused
    figure_ids: tuple[str, ...]
    chart: ChartSpec | None
```

`CitedFigure` gains `section`. `StatedFigure` gains `section` — the section a surface *claims* it
placed the figure in, which is a claim and therefore reconciled rather than trusted.

### A surface states its sections, and is not asked to imply them

`SurfaceLanguage` gains `sections: tuple[str, ...]` — the ordered sections that language claims it
presented — reconciled against the ordered section ids in `bundle.sections`.

Deriving that tuple from the figure rows instead was the obvious shortcut and it is wrong in two
directions at once. A **refused** section carries no figures by definition, so it would never appear
in a derived tuple: the required refusal heading could be absent from every surface while
reconciliation succeeded, which defeats the "a refused family still renders" rule below. And a
section dropped from *both* languages would still produce two matching derived tuples, so the
cross-language comparison would pass on a report that silently lost a whole analysis. Coverage
inferred from content can only ever detect a disagreement between surfaces, never a shared omission;
the bundle is the thing that knows what should be there, so the claim is compared against the bundle.

This adds one refusal reason, `section_not_presented`, for a surface whose section claim does not
match the bundle's — distinct from the two cross-language reasons, which stay for the case where the
surfaces disagree with each other rather than with the bundle.

`ORDERED_SECTIONS` covers **figure-bearing analysis sections only**. The template's existing caveats,
commentary, citations and provenance sections hold no `CitedFigure`, so they are not `Section`s and
are unchanged by this model. They keep their present place in the navigation and on every surface.

### Caveats are bound to sections too

`RRA-008` caveats are per-family — "a caveat naming the truncated window" belongs to the comparison,
not to the report — and the chart-failure path below emits a caveat scoped to one section. But
`SurfaceLanguage.caveats` is a flat tuple of codes and `reconcile` compares
`frozenset(entry.caveats)` against `frozenset(bundle.caveats)`, with no section binding. A surface
could therefore render the comparison's truncation caveat under the basket section and reconcile
perfectly — the same hole `figure_misplaced` closes for figures, left open for the text that
qualifies them.

A caveat therefore becomes a `(code, section)` pair, with `section` `None` for a report-level caveat
that belongs to no single analysis. Report-level caveats render in the existing caveats section;
section-scoped caveats render inside the section they qualify. No new refusal reason is needed: the
existing comparison against `bundle.caveats` now compares pairs, so a misplaced caveat fails it
exactly as a missing one does.

### A refused family still renders

`RRA-008` refuses the affected analysis and not the report. A section whose family refused renders
its heading and its governed reason, in both languages, on all three surfaces. Omitting it was
considered and rejected: a missing section is indistinguishable from an analysis that was never
attempted, and the reader cannot tell "there was nothing to show" from "we could not show it."
Absence is never the disclosure.

### The comparison section carries two governed modes, not one

`RRA-008` requires the current window compared to a prior window of equal length "for
period-over-period **and** year-over-year." Both are governed results, so both are figures in the
comparison section, and each needs its own stable identity — `_identity` already derives fact and
citation ids from `(metric, scope, formula_version)`, so the mode belongs in `scope`, giving
`("period_over_period",)` and `("year_over_year",)` distinct ids for the same metric name.

Deriving a single unnamed current/prior pair by splitting the trend satisfies neither requirement
fully: it produces one comparison and leaves the reader unable to tell which window it compared. The
two modes also refuse independently — a dataset spanning eight months has period-over-period coverage
and no year-over-year coverage at all — and `RRA-008` refuses "the affected comparison, and not the
report," so one mode refusing must leave the other standing inside the same section.

### New refusal reasons

Five join `GOVERNED_REASONS`, the existing gate that keeps a refusal record free of customer
content:

- `unknown_section` — a surface names a section outside `ORDERED_SECTIONS`
- `figure_misplaced` — a stated figure's section differs from the bundle's
- `section_not_presented` — a language's section claim does not match `bundle.sections`
- `section_coverage_differs_by_language` — the section sets differ between Arabic and English
- `section_order_differs_by_language` — the order differs between them

The last two exist because per-language reconciliation is individually satisfiable. A
surface that drops the concentration section from Arabic alone reconciles perfectly language by
language, exactly as the existing `figure_coverage_differs_by_language` comment describes for rows.
They do not subsume `section_not_presented`, which catches the omission both languages agree on.

`Section` validates its own state against `{SECTION_PRESENT, SECTION_REFUSED}` before it applies the
reason rules. Checking only the two valid state/reason *combinations* leaves an unknown state such as
`"pending"` with no reason passing construction, and a renderer branching on `state == SECTION_REFUSED`
then draws it as present — a section in an invented state rendering as a normal one. Membership is
checked first so a malformed state fails closed.

## Charts

### Three kinds, and why not four

| Section | Chart | Source |
|---|---|---|
| Overview | bar | RRA-004 headline figures |
| Comparison | grouped bar | current window against prior, per governed mode |
| Concentration | line | `RRA-008`: "the cumulative share curve" |
| Growth | grouped bar | price effect, volume effect, total change |
| Basket | bar | attach rate per dimension value |

Growth decomposition is conceptually a waterfall and is rendered as a grouped bar. A fourth chart
kind adds a branch to every dispatching function in the chart module, and Code Health scores
*Overall Code Complexity* as the mean cyclomatic complexity per function; three kinds keep that mean
low enough for a new file to reach 10.00. The two effects shown beside the total carry the same
statement.

### Geometry is exact until the last step

`CitedFigure` carries `value: Decimal` alongside `renderings`. Chart geometry is computed in
`Decimal` and converted to a coordinate only when the coordinate is written. No governed figure
passes through binary floating point on the web or PDF path, so `KHEPRI-DEC-005`'s rule that binary
floating-point values are never authoritative financial facts is untouched by those two surfaces.
`KHEPRI-DEC-005` already anticipates charts: "Charts consume fact-package series and never
independently calculate business figures."

### A chart cannot plot what the bundle did not supply

`ChartSpec.figure_ids` must be a subset of its own section's `figure_ids`, and every figure a chart
plots must also appear in that language's `stated`. The first is a structural guarantee rather than
a validation: a chart can only reference figures the section already declared, and those are already
reconciled by exact string comparison. The second closes the remaining gap. Together they give the
chart the whole text-reconciliation guarantee without a parallel mechanism.

### Right-to-left is a rendering duty, proven per surface

An Arabic table already reverses through CSS logical properties, but an SVG `<rect x="...">` and a
spreadsheet category axis both default to left-to-right regardless of the declared direction. An
Arabic chart could therefore plot its first category on the wrong side while every text cell
reconciles, because `reconcile` compares strings. Mirroring is verified by each renderer's own
tests, in the same division of labour the codebase already applies to PDF tagging and reading
direction: direction is declared to the bundle and proven by the renderer.

### The chart module computes geometry; the template writes the markup

A chart function returning an SVG string cannot be rendered by these templates. `build_environment()`
sets `autoescape=True` unconditionally, and `html.py` states the rule it exists to hold: "nothing
reachable from the bundle is ever marked safe … a page with one `|safe` in it has an escaping
convention, not an escaping guarantee." A `{{ section.chart_svg }}` holding a Python string therefore
reaches the reader as `&lt;svg …`, and the page shows chart source as text — on the web surface and,
through template inheritance, on the printed one.

The two available exits are a `|safe` exemption and a `Markup` object, and both are the same exit:
they move the escaping decision from the environment into whoever remembers to apply it, on the one
path customer-derived labels travel. The chart's own axis labels are customer values.

So the boundary moves instead. `charts.py` returns a **view model of computed geometry** — coordinates
already resolved to strings, labels as ordinary text — and a Jinja macro writes the `<svg>`, `<rect>`,
`<path>` and `<title>` elements. The tags are template source, which is trusted because it is source;
every label passes through the same autoescaping as every other cell, which is what makes a value
named `<script>` inert here for the same reason it is inert in a table.

```python
@dataclass(frozen=True, slots=True)
class ChartView:
    kind: str
    title: str
    description: str
    marks: tuple[ChartMark, ...]     # x, y, width, height / path, already strings
    labels: tuple[str, ...]
```

`render_chart` becomes `build_chart(...) -> ChartView | None`, and `None` still means undrawable. The
macro lives beside `report.html.j2` and is included by it, so the print surface inherits it with the
rest of the parent template and the one-template guarantee is untouched. No new escaping policy, no
exemption, and the SVG is verifiable by asserting the *rendered page* contains `<svg` — which the
string-returning design could never have asserted, because it never would have.

### The accessible table is never replaced

Every section presents its table on every surface, chart or no chart. The SVG carries `role="img"`
and `aria-labelledby` referencing a `<title>` and `<desc>`. This keeps `RRA-006`'s accessible-tables
requirement satisfied independently of what any chart does.

## Native workbook charts and the DEC-005 amendment

### Why an amendment is required

An XlsxWriter chart series addresses numeric cells. Every governed figure in the workbook is
deliberately written as the decimal **string** the package computed, because Excel stores numeric
cells as IEEE 754 doubles and `KHEPRI-DEC-005` forbids binary floating point as an authoritative
financial fact. A native workbook chart therefore cannot be added without an amendment, and the
amendment must be approved by the named active authority before any code is written.

Rendering the web SVG to an image and placing it in the worksheet was considered. It needs no
amendment and produces a chart byte-identical across all three surfaces. It was rejected in favour
of native charts on the instruction that each surface carry a chart native to it; the trade is a
governance amendment and a workbook chart that will not look identical to the web and PDF chart.

### The bounded permission

The amendment permits numeric cells **solely as chart series addresses**, on a dedicated per-language
worksheet that carries no authoritative figure and no citation:

- Numeric cells appear only on `<lang>_chartdata`.
- A chartdata worksheet carries no citation identifier, so no reader is ever cited to one.
- Chartdata cells are excluded from `SurfaceLanguage.stated`, so `reconcile` neither sees nor
  accepts them as a presentation of a figure.
- A test asserts that for every numeric chartdata cell, the canonical decimal string of its value
  equals the authoritative string cell it mirrors. The numeric copy is proven a faithful copy at
  write time rather than assumed to be one.

The authoritative figure remains the string on the section worksheet. The numeric cell is an address
a chart points at.

### Which document should carry the permission

`KHEPRI-DEC-008` is `proposed` and would supersede `KHEPRI-DEC-005`, so amending `KHEPRI-DEC-005`
risks writing a permission into a document that is replaced. Three placements were considered. The
permission belongs in `KHEPRI-DEC-005` because that is where the prohibition it narrows is written,
and a permission separated from its prohibition is how a bounded exception becomes a general one.
`KHEPRI-DEC-008` addresses the deployment and runtime target, not the numeric-fact rule, so it is
the wrong home and its supersession would need to carry the clause forward regardless. A standalone
decision was rejected as heavier than the exception warrants. Whoever advances `KHEPRI-DEC-008`
should carry the amended clause across with the rest of `KHEPRI-DEC-005`.

## Worksheet layout

```
ar_overview  ar_comparison  ar_concentration  ar_growth  ar_basket
ar_citations ar_chartdata
en_overview  en_comparison  en_concentration  en_growth  en_basket
en_citations en_chartdata
provenance
```

Fifteen worksheets. Provenance stays single and shared, as it is today. A refused section still
receives its worksheet carrying the governed reason, matching the web and PDF rule.

## Failure levels

Three levels, deliberately with different blast radii.

**A family refuses.** Preconditions fail per `RRA-008`. The section is `SECTION_REFUSED` with a
governed reason, the report is delivered, and every other section is unaffected. This is the common
case and must never escalate.

**A surface cannot reconcile.** `reconcile` raises `BundleRefused`, which the existing bundle path
turns into `OUTCOME_INCOMPLETE` with `surface_failed`, satisfying `RRA-006`'s requirement that
partial export failure be an incomplete bundle rather than a mixture of versions. Unchanged
behaviour; more ways to trigger it.

**A chart cannot be drawn.** A single-point series, an all-zero series, or a plotted figure whose
`value` is `None`. The section renders with `chart=None` **and a governed caveat**. It does not
refuse: the table is the authoritative presentation and the chart is an aid, so a rendering concern
must not suppress governed analysis. The caveat rather than a silent `None` is what preserves the
distinction between nothing to show and unable to show.

## Verification

Beyond the golden-dataset tests `RRA-008` already specifies:

- A figure stated in the wrong section refuses.
- A section present in `bundle.sections` and absent from a language's section claim refuses, **including
  when it is absent from both languages** — the case a derived tuple could never catch.
- A refused section appears in the section claim even though it carries no figures.
- A `Section` constructed with a state outside `{SECTION_PRESENT, SECTION_REFUSED}` raises.
- Section coverage differing by language refuses; section order differing by language refuses.
- Period-over-period and year-over-year each emit distinct fact and citation ids, and one refusing
  leaves the other standing in the section.
- A rendered page contains a literal `<svg` element — asserted on the page, not on a returned string.
- A customer value named `<script>` appears escaped in a chart label on the rendered page.
- Concentration and attach rate refuse with `aggregate_unavailable` until the `RRA-004` amendment
  records approval, and their sections render that reason.
- Items per transaction is derived from `METRIC_UNITS` and `METRIC_TRANSACTIONS`, never from row count.
- A refused section renders its governed reason on all three surfaces in both languages.
- A section-scoped caveat rendered under the wrong section refuses.
- A report-level caveat renders in the caveats section and a section-scoped one inside its section.
- A chart plotting a figure absent from `stated` refuses.
- Arabic chart mirroring, verified separately for SVG and for the workbook.
- Single-point and all-zero series produce `chart=None` plus a caveat, with the section delivered.
- Every numeric chartdata cell matches the authoritative string cell it mirrors.
- No authoritative figure or citation appears on a chartdata worksheet.
- `stated` never contains a chartdata cell.
- The PDF places each section on its own page.

## Delivery

**The four analysis families stay four independently verifiable slices.** An earlier revision of this
design combined them with the section model and the chart work into one slice and recorded the
increased Code Health risk as the price. That was the wrong trade and it is withdrawn.
`2026-08-02-rra-comparative-analysis-design.md` already states that `RRA-008` implementation is "four
independently verifiable slices, one per analysis," and `AGENTS.md` requires that a slice never widen
beyond its stated boundary. Recording a cost does not purchase permission to incur it: the Code
Health gate requires every new file to score exactly 10.00 and permits no tracked hotspot to decline,
so a combined slice puts six or more new files in front of that gate at once and one violation blocks
the correct parts along with the bad one. The four-slice sequencing exists precisely to bound that,
and the shared section, chart, and renderer work layers through separately verifiable changes.

Eight slices, each independently mergeable and independently verifiable:

| # | Slice | Gated on |
|---|---|---|
| 0a | `KHEPRI-DEC-005` amendment — numeric chart cells | — |
| 0b | `RRA-004` amendment — concentration curve and transaction membership | — |
| 1 | Section model in `bundle.py`: types, placement and section-claim reconciliation, caveat binding | — |
| 2 | Period comparison, both governed modes | — |
| 3 | Concentration | 0b |
| 4 | Growth decomposition | — |
| 5 | Basket structure — items per transaction; attach rate refuses until 0b | partially 0b |
| 6 | Chart view model, macro, and the web and PDF surfaces | 1 |
| 7 | Workbook: a sheet per section, then native charts | 1, 0a |

Both approval gates are independent of each other and neither blocks slice 1. The two amendments can
be proposed in parallel and neither is on the critical path for the section model, comparison, or
growth. Slices 2 and 4 depend on nothing but the fact package as it already stands.

Slices 3 and 5 are written to be *implementable before* gate 0b clears — each emits its governed
refusal (`aggregate_unavailable`) and its section renders that reason, which is deliverable behaviour
rather than a stub. When the amendment lands, each is completed by a further slice that consumes the
new aggregate and replaces the refusal with the figures. That way a pending human approval never
leaves a branch parked.

**One collision is predictable and belongs in the pull request before it happens.** `CitedFigure`
gains a required `section` field, `SurfaceLanguage` gains a required `sections` field, and the caveat
type changes shape — all three are shared DTOs, so any branch that constructs one will fail to build
once slice 1 merges, and the second to merge fixes the fixtures. This is the same class as the
`alembic` `down_revision` sibling collision the repository's change discipline already names.

`PACKAGE_VERSION` moving to `rra004.package.v2` in slice 0b is a second, larger version of the same
thing: it changes the package document shape and therefore every stored digest derived from it. It is
confined to that slice deliberately, so the shape change arrives on its own and is not diagnosed
through a renderer.

## Out of scope

- Separate HTML documents per section. The web report remains one document per language with
  page-like sections and navigation, which is what `RRA-006`'s "navigable web report" requires.
  Multiple documents would fork the web and PDF paths and break the one-template guarantee.
- Client-side scripting of any kind. The template Chromium renders to PDF must not depend on script
  timing, and content hidden behind interaction raises a question about what the reader actually saw
  that the fail-closed model would have to answer.
- Two-dimension breakdowns, forecasting, customer-defined metrics, and cohort or repeat-purchase
  analysis, all of which `RRA-008` and its design place outside this work.
- Charts in the narrative. `RRA-005` inputs are unchanged.

## What this design does not do

It creates no amendment document, no registry entry, no approval package, and no code. Neither the
`KHEPRI-DEC-005` amendment nor the `RRA-004` amendment exists until it is written and its registry
entry records approval evidence from the named active authority. A design document is not authority,
and neither is a merged pull request.

It also does not correct the two governed specification documents whose closing prose contradicts
their registry state. That drift is recorded at the top of this document and left for a change that
carries its own approval.
