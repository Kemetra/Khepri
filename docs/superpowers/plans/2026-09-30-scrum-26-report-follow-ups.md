# SCRUM-26: report wording and Arabic presentation follow-ups (A3b, A4, A9, A11)

> The plan for SCRUM-26, and the plan and RED evidence for its first slice (A11). The
> findings are recorded in `2026-09-29-scrum-21-u1-acceptance-evidence.md` and
> `2026-09-30-scrum-21-u1-acceptance-rerun.md`. The owner accepted SCRUM-21 on
> 2026-09-30 and moved these four into SCRUM-26.

## Mapping

Registry state is read from `governance/registry.yaml` at `10a9bb8`. Every specification
named here is `state: active`. `RRA-005` states its requirements as bullets and numbers
no FRs, so it is cited by requirement.

| Finding | Where it is composed | Governing specification | Disposition |
|---|---|---|---|
| **A11**: Arabic PDF breakdown dates wrap | `report.print.css` | `RRA-006`: "tagged and readable PDF", "right-to-left Arabic layout". The same authority as SCRUM-25 A1 and A2 (#629). | **Slice 1, this PR.** |
| **A4**: two period-comparison refusals read as a contradiction | `wording.py`, `REFUSAL_WORDING["section"]` (`prior_window_absent`, `coverage_structurally_incompatible`) | `RRA-009` §Refusals, the five-part rule. A sentence that is false where it is printed is a wrong second part. | **Owner proposal.** The caveat code carries its mode (`revenue_delta_absolute.year_over_year:prior_window_absent`), but the prose is keyed by reason alone. Naming the basis needs messages keyed by mode, which moves the catalogue counts in `RRA-009` §Refusals: a specification amendment. A rewording inside the current keys cannot name the basis, so it would not fix A4. |
| **A9**: commentary figures unformatted, an agreement error, English measure codes and Latin digits in Arabic | `deterministic_narrative.py` (`_english`, `_arabic`, `_readable`, `_fact_figure`) | `RRA-005`: "wording may differ without changing meaning"; "reject unsupported numbers ... or unsafe label transformations". | **Split.** The agreement error and governed measure names are a candidate slice 3, if `narrative.validate` accepts them. Formatted figures and Arabic-Indic digits go against the module's recorded rule that it quotes a supplied figure verbatim and has no mandate to change its digits. That needs an owner reading, not a slice. |
| **A3b**: "Dairy (category)" in Arabic | `basket.attached_label_of`, carried as `CitedFigure.label` | No single presentation authority. `RRA-008` states what a fact is and excludes customer surfaces. The label feeds `CitedFigure.as_document` and so the bundle digest (`RRA-006`). | **Owner proposal, not a slice.** See below. |

### A3b: the options for the owner

The qualifier is English because it is the dimension's semantic key, fixed into one
label string before any language is chosen. The renderer gets `Dairy (category)` and
cannot tell the qualifier from the value.

1. **The bundle carries the dimension as its own governed token** and the label carries
   the bare value. Each surface words the dimension per language from `DIMENSION_NAMES`.
   This changes the bundle document and therefore the digest for new runs. Stored bundles
   stay immutable under their recorded identity. Needs an `RRA-006` amendment naming the
   field.
2. **The renderer recognises the trailing ` (product)` / ` (category)` and words it.**
   Render-only, and no digest moves. But one string format is then pinned in two places,
   and a product literally named `Tea (category)` is misread. `RRA-005`'s "unsafe label
   transformations" argues against it.

**Recommendation: option 1**, proposed as an `RRA-006` amendment before any code.

## Slice 1: A11

### Cause, measured

Chromium, print media, 673 px (the A4 measure the print sheet's `@page` leaves), on the
document `PdfReportRenderer` printed from the SCRUM-21 fixture:

| | Date column | Date's own width | Result |
|---|---|---|---|
| English | 101 px | 73 px + 16.8 px padding | one line |
| Arabic | 87 px | 73 px + 16.8 px padding | `2026-01-` / `05`, all 55 dates |

Since #629, header cells may wrap on paper. The Arabic headers are longer, and table
layout gives their columns the width the date column needed, 3 px short of the date.
This is layout, not bidi. The hyphen is simply where the line may break.

### Change

`report.print.css`: the row label's content box is never narrower than ten digits,
`box-sizing: content-box; min-inline-size: 10ch` on `.figures th[scope="row"]`. An ISO
date is eight digits and two hyphens, so it fits.

**Not `nowrap`.** A row label is also a product or branch name. One that could not wrap
would widen the table past the page, which is A1 again. With labels lengthened to 60
characters, the chosen rule still prints every table inside `main`.

No template, renderer module, bundle, wording or governed artifact changes. The screen
sheet is unchanged.

### Tests (RED at `10a9bb8`)

`tests/test_rra006_printed_fit.py::test_no_printed_breakdown_date_wraps_in_either_language`:

- at least five ISO dates are measured per language, so a fixture that stopped
  publishing the by-period breakdown fails;
- no date takes more than one line;
- every row label keeps `white-space: normal`, so `nowrap` cannot pass.

The existing A1 and A2 tests in the same module stay green.

## After slice 1

- The mapping and the A3b options are posted on SCRUM-26.
- Acceptance criterion 4, parity on the rendered PDF in the pinned image, is checked
  once per changed item. For A11: both languages, rendered in `khepri-runtime:staging`
  with the SCRUM-21 re-run's compose override.
