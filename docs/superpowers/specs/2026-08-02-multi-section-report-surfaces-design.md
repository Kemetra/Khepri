# Multi-section report surfaces and charts — design

Date: 2026-08-02

Authority: none. This document designs an amendment to `KHEPRI-DEC-005`, which has not been
proposed. `RRA-006` and `RRA-008` are `approved` in `governance/registries/` and both bound the work
below, but nothing here is approval and nothing here changes a registry.

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

### New refusal reasons

Four join `GOVERNED_REASONS`, the existing gate that keeps a refusal record free of customer
content:

- `unknown_section` — a surface names a section outside `ORDERED_SECTIONS`
- `figure_misplaced` — a stated figure's section differs from the bundle's
- `section_coverage_differs_by_language` — the section sets differ between Arabic and English
- `section_order_differs_by_language` — the order differs between them

The third and fourth exist because per-language reconciliation is individually satisfiable. A
surface that drops the concentration section from Arabic alone reconciles perfectly language by
language, exactly as the existing `figure_coverage_differs_by_language` comment describes for rows.

## Charts

### Three kinds, and why not four

| Section | Chart | Source |
|---|---|---|
| Overview | bar | RRA-004 headline figures |
| Comparison | grouped bar | current window against prior |
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
- Section coverage differing by language refuses; section order differing by language refuses.
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

**This deviates from a written intent and the deviation is deliberate.**
`2026-08-02-rra-comparative-analysis-design.md` states that `RRA-008` implementation is "four
independently verifiable slices, one per analysis." The instruction governing this work is a single
combined slice covering the section model, all four analysis families, and charts on three surfaces.

The cost of the deviation is recorded here so it is not discovered later. The repository's Code
Health gate requires every new file to score exactly 10.00 and permits no tracked hotspot to
decline, and `src/khepri/rra/api.py` is a tracked hotspot. A combined slice presents six or more new
files to that gate at once, and a single violation in any of them blocks the whole merge, including
the parts that are correct. The four-slice sequencing exists to bound that risk.

Ordering within the slice is fixed by dependency regardless:

1. `KHEPRI-DEC-005` amendment proposed, and approved by the named active authority. Nothing that
   writes a numeric workbook cell may be written before this records approval evidence. This is the
   only approval gate in the work; every other step is authorized by `RRA-006` and `RRA-008` as they
   already stand.
2. Section model in `bundle.py`, with the four new refusal reasons, the section-bound caveat pair,
   and their tests.
3. The four analysis families, each with its golden-dataset tests.
4. The chart module, then the three renderers.

Steps 2 through 4 do not depend on step 1 and can proceed while the amendment is pending. Only the
workbook's chart path is gated.

**One collision is predictable and belongs in the pull request before it happens.** `CitedFigure`
gains a required `section` field and the caveat type changes shape — both are shared DTOs, so any
branch that constructs either will fail to build once this merges, and the second to merge fixes the
fixtures. This is the same class as the `alembic` `down_revision` sibling collision the repository's
change discipline already names.

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

It creates no amendment document, no registry entry, no approval package, and no code. The
`KHEPRI-DEC-005` amendment does not exist until it is written and its registry entry records
approval evidence from the named active authority. A design document is not authority, and neither
is a merged pull request.
