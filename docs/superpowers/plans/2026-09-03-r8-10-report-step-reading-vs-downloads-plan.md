# R8-10 (journey half) — the report step puts the report and evidence before the other formats

**Authority:** active `RRA-010`. **Scope:** `journey/templates/report.html.j2`, `assets/report.js`,
`assets/journey.css`, two presentation-only keys in `copy.py`, and `tests/test_rra_journey_pages.py` —
one of the three test files `RRA-010`'s Scope names for extending assertions. `test_rra_journey_report.py`
is not among them and is not touched.
**Roadmap task:** `R8-10`, *"analysis quality and evidence entry points to the journey and shell; user
understands what was computed, caveated, and refused before downloading"* — its journey half only.
The shell half is `RCA-002`'s and is not touched.

**Status:** bounded plan. Its RED tests land with it. Its finding is the one
`2026-09-03-rra010-journey-adoption-reading.md` recommends acting on: the entry points already exist as
links, and what the step lacks is presentation.

---

## Three checks against the tree, run before this plan was written

### 1. The data side of `R8-10`'s journey half is already met

The web report surface begins with the analysis-quality summary — `rendering/templates/report.html.j2:54`
renders `quality_summary(answered, caveated, refused, chrome)` in the page header since `#350` — with a
status badge on every section and a refusal panel on every refused one. The evidence surface, a separate
document by `RRA-009`'s design, carries a citation link and a drawer beside every figure since `#358`;
the web report does not link to it, because citation identifiers are Audit-tier. The journey's report
step (`report.js`) is the one place that links both, in both languages, alongside the PDF and Excel. A
reader who opens the web report sees what was computed, caveated, and refused; the evidence surface
says why. No new read is needed, and `RRA-010`'s third bounding test forbids one.

### 2. What the step lacks is a distinction it can make with what it has

`report.html.j2:8` renders one `#report-links` holder and `report.js` fills it with seven `.report-card`
links in one `.report-grid`, equal in weight and unlabelled as to kind. Nothing says the web report is
the place to look first, or that three of the seven are files to download rather than pages to open.
Grouping the seven under two labelled headings — the report and its evidence, then the other formats —
and giving the page-language web report the first position and a primary weight is a change to how
an existing surface is presented. It adds no surface, route, state, or read, so all three of
`RRA-010`'s bounding tests hold.

**The headings name content, not mechanism, and review is why.** An earlier draft labelled the groups
"Open in your browser" and "Downloads". That was false on this tree: `_artifact_response`
(`report_api.py:557-565`) sends `Content-Disposition: attachment` for every surface, the web report
included, and `tests/test_rra006_report_artifact_api.py:92` asserts it. Clicking the web report card
saves an HTML file; nothing "opens". Whether the two HTML surfaces should be served inline is a
question for `RRA-006`, which governs the render targets, and is **out of this slice's authority** —
recorded below for the owner rather than changed here.

### 3. The two headings are presentation-only copy

`RRA-010` Scope admits *"presentation-only copy keys in `copy.py` — keys naming a control, a state, or
an affordance."* A heading reading "Report and evidence" or "PDF and Excel" names the group of
controls beneath it. Neither describes a metric, refusal, caveat, or figure, so `RRA-009` and `RRA-011`
are not touched. `copy.py:338` already fails the import when one language lacks a key the other has.

---

## What is being built

- `report.html.j2`: inside `#report-links`, two `<section class="report-group">` elements, each labelled
  by its own `<h2>` — `copy.report_and_evidence` then `copy.other_formats` — each holding a
  `.report-grid` with `data-group="read"` or `data-group="formats"`. The data attributes the module reads stay on the
  holder. The holder stays `hidden` until the bundle is complete, as today.
- `report.js`: each link tuple carries its group; the web report and evidence links go to the read
  grid, the PDF and Excel links to the formats grid. The web report in the page's own language is
  first in the read grid and carries `report-card--primary`. Nothing else in the module changes.
- `journey.css`: a heading rule for `.report-group h2` and a weight rule for `.report-card--primary`,
  logical properties only. The `.report-grid` single-column collapse at 640px already applies to both
  grids.
- `copy.py`: `report_and_evidence` and `other_formats`, in both languages.

## RED tests — the deliverable

`tests/test_rra_journey_pages.py`, strict-xfail until the implementation commit:

1. `test_the_report_step_leads_with_the_report_and_evidence[en, ar]` — the served page holds
   two `report-group` sections in that order, each labelled by an `h2` whose id its `aria-labelledby`
   names, worded from `JOURNEY_COPY` for that language; and one grid per group.
2. `test_the_report_module_files_every_surface_in_its_group` — from the module's source, the seven link
   tuples carry a group each: `web` and `evidence` read, `pdf` and `excel` formats; the page-language
   web report is marked primary; and no tuple lacks a group, so an eighth link cannot go ungrouped.
3. `test_the_group_headings_name_an_affordance_and_no_figure` — the two new keys exist in both languages
   and neither language's wording contains a digit, a per-cent sign, or a currency mark: a heading that
   starts carrying a figure has left `RRA-010`.

The three tests in `test_rra_journey_report.py` are unchanged: the links are still absent from the
initial HTML, still exactly seven, still built only after `bundle_complete`.

## Verification `RRA-010` requires

- Both languages, in every test above.
- The browser viewport test (`test_journey_pages_fit_viewport_and_keep_operable_targets`) already covers
  the report step at 1180 and 390 px in both languages and is run locally before merge, because
  Chromium never runs in CI.
- No physical directional property enters `journey.css`; the existing scan re-asserts it.

## Out of scope, and why

- Rendering the quality summary **on** the journey page. That is a new read (`RRA-010` test 3) and
  the subject of the open owner decision.
- Any change to what the report API serves, to the artifact routes, or to the shell.
- A `download` attribute on the file links. It changes what the browser does with an already-served
  route; not needed for the distinction this slice makes.
- **Serving the HTML surfaces inline.** Every surface is an attachment today (check 2). If the owner
  wants the web report to open in the browser rather than save, that is a response-header change in
  `report_api.py` under `RRA-006`, with its own test (`test_rra006_report_artifact_api.py:92`) to
  amend. Filed here as a finding; not this slice's to make.
