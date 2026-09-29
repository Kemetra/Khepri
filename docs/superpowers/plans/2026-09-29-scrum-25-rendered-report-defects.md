# SCRUM-25: the rendered-report defects A1-A3 from SCRUM-21's first acceptance run

> Plan and RED evidence for one slice. The defects are recorded in
> `2026-09-29-scrum-21-u1-acceptance-evidence.md`. The owner decided on 2026-09-29 that
> SCRUM-21 is not accepted until they are fixed and the PDFs are rendered again in the
> pinned image.

## Authority

| Defect | Files | Governing specification | Why that one |
|---|---|---|---|
| A1: printed tables leave the page in Arabic | `report.print.css` | `RRA-006` | It requires a "tagged and readable PDF", "right-to-left Arabic layout", and every figure rendered. A1 drops a column of figures from the Arabic PDF. `RCA-010`:280 and `RRA-016` "Not in scope" both attribute `report.print.css` to `RRA-006`, `RRA-012` and `RRA-015`. |
| A2: appendix codes break mid-word | `report.print.css` | `RRA-006` | The same readability requirement. The print sheet was added under `RRA-006` (#31), and the screen rule it overrides came from the same slice set (#28). |
| A3: chart labels drawn over bars | `charts.py`, the `.chart__label` comment in `report.css` | `RRA-015` §Scope, "axis and label geometry"; `FR-183` | `charts.py` is named there for exactly this. |

**Not cited, on purpose.** `RRA-015` says "No other print rule changes", and `RRA-018` says
"changing no existing rule". Both limit what *those* specifications grant. Neither governs
a fix made under `RRA-006`.

No template, route, renderer module, bundle, wording or governed artifact changes.

## Causes, measured

The measurements are in Chromium, under print media, at the A4 measure the print sheet's
`@page` leaves (178 mm, 673 px). They were taken on the document `PdfReportRenderer`
actually printed.

- **A1.** `report.css` sets `thead th { white-space: nowrap }`. The Arabic breakdown
  headers are long, so three tables become 18-42 px wider than the page. The print
  sheet's `.scroller { overflow: visible }` then spills them past the left edge in RTL.
  English fits.
- **A2.** `report.css` sets `code { word-break: break-all }`. That makes every column's
  min-content one character wide, so seven columns of codes (835 px at their longest
  words) are squeezed to fit 673 px. Every column's widest word splits, including
  `value`, `monetary` and every metric-code segment.
  - `overflow-wrap: break-word` alone keeps words whole but overflows the page by 161 px.
    That is A1 again.
  - The fix keeps the three governed-vocabulary columns (metric, kind, unit) unbreakable
    and lets the opaque figure and citation references wrap.
- **A3.** `charts._label` sets `y = CHART_HEIGHT`, which is the foot of the plot itself.
  Every bar that reaches the zero line at the foot sits under its own label. Descenders
  fall outside the viewBox, and the axis unit shares that foot.

## Change

1. **`report.print.css`:**
   - `thead th { white-space: normal }`.
   - `code { word-break: normal; overflow-wrap: anywhere }`.
   - The metric, kind and unit cells of the evidence figures table get
     `overflow-wrap: normal`.
   - `td.figure` stays `nowrap`.
   - The screen sheet is unchanged, so `RRA-015` `FR-193`'s 390 px / 200% evidence reflow
     is untouched.
2. **`charts.py`:**
   - `PLOT_HEIGHT = 320` is what the domain scales to. Marks, the baseline and the domain
     keep their coordinates.
   - `CHART_HEIGHT` becomes `PLOT_HEIGHT` plus a label band and an axis-unit row.
   - Labels move into the band.
   - The axis unit keeps its #481 placement at the start edge and canvas foot, which is
     now a row of its own.
3. **Existing geometry tests.** Assertions that equated the plot foot with
   `CHART_HEIGHT` now name `PLOT_HEIGHT`. None is loosened.

## Tests (RED at `7250c81`)

- `tests/test_rra006_printed_fit.py`:
  - no printed table leaves `main`, in either language (A1);
  - no metric, kind or unit code splits across lines (A2).
- `tests/test_rra015_chart_label_band.py`:
  - labels sit below the plot in every kind and language;
  - no chart word meets a mark or the canvas edge on the web report and on the printed
    document, in both languages (A3).
- `tests/rra_printed_support.py`: the SCRUM-21 file shape, with category, branch and
  paired invoices. It includes a `PagePrinter` that records the document it prints.

Each browser test asserts that its subject is present (a five-column table; `value` and
`monetary`; a bar and a grouped-bar chart), so a fixture that stopped producing it fails
instead of passing on nothing.

## After merge

The SCRUM-21 method is re-run on the new `main`, including the PDFs rendered in
`khepri-runtime:staging`. The acceptance record's status banner is replaced only then.
