# R8-10 (journey half) — the report step separates reading from downloading

**Authority:** active `RRA-010`. **Scope:** `journey/templates/report.html.j2`, `assets/report.js`,
`assets/journey.css`, two presentation-only keys in `copy.py`, and `tests/test_rra_journey_report.py`.
**Roadmap task:** `R8-10`, *"analysis quality and evidence entry points to the journey and shell; user
understands what was computed, caveated, and refused before downloading"* — its journey half only.
The shell half is `RCA-002`'s and is not touched.

**Status:** bounded plan. Its RED tests land with it. Its finding is the one
`2026-09-03-rra010-journey-adoption-reading.md` recommends acting on: the entry points already exist as
links, and what the step lacks is presentation.

---

## Three checks against the tree, run before this plan was written

### 1. The data side of `R8-10`'s journey half is already met

The web report surface opens with the analysis-quality summary — `rendering/templates/report.html.j2:54`
renders `quality_summary(answered, caveated, refused, chrome)` in the page header since `#350` — and
every figure on it links to its evidence; the evidence surface carries a drawer beside every figure
since `#358`. The journey's report step (`report.js:18-24`) links both surfaces, in both languages,
alongside the PDF and Excel downloads. A reader who opens the web report sees what was computed,
caveated, and refused before downloading anything. No new read is needed, and `RRA-010`'s third
bounding test forbids one.

### 2. What the step lacks is a distinction it can make with what it has

`report.html.j2:8` renders one `#report-links` holder and `report.js` fills it with seven `.report-card`
links in one `.report-grid`, equal in weight and unlabelled as to kind. Nothing says the web report is
the place to look first, or that three of the seven are files to download rather than pages to open.
Grouping the seven under two labelled headings — pages to open, files to download — and giving the
page-language web report the first position and a primary weight is a change to how an existing
surface is presented. It adds no surface, route, state, or read, so all three of `RRA-010`'s bounding
tests hold.

### 3. The two headings are presentation-only copy

`RRA-010` Scope admits *"presentation-only copy keys in `copy.py` — keys naming a control, a state, or
an affordance."* A heading reading "Open in your browser" or "Downloads" names an affordance. Neither
describes a metric, refusal, caveat, or figure, so `RRA-009` and `RRA-011` are not touched. `copy.py:338`
already fails the import when one language lacks a key the other has.

---

## What is being built

- `report.html.j2`: inside `#report-links`, two `<section class="report-group">` elements, each labelled
  by its own `<h2>` — `copy.open_online` then `copy.downloads` — each holding a `.report-grid` with
  `data-group="open"` or `data-group="download"`. The data attributes the module reads stay on the
  holder. The holder stays `hidden` until the bundle is complete, as today.
- `report.js`: each link tuple carries its group; the web report and evidence links go to the open
  grid, the PDF and Excel links to the download grid. The web report in the page's own language is
  first in the open grid and carries `report-card--primary`. Nothing else in the module changes.
- `journey.css`: a heading rule for `.report-group h2` and a weight rule for `.report-card--primary`,
  logical properties only. The `.report-grid` single-column collapse at 640px already applies to both
  grids.
- `copy.py`: `open_online` and `downloads`, in both languages.

## RED tests — the deliverable

`tests/test_rra_journey_report.py`, strict-xfail until the implementation commit:

1. `test_the_report_step_separates_pages_to_open_from_files_to_download[en, ar]` — the served page holds
   two `report-group` sections in that order, each labelled by an `h2` whose id its `aria-labelledby`
   names, worded from `JOURNEY_COPY` for that language; and one grid per group.
2. `test_the_report_module_files_every_surface_in_its_group` — from the module's source, the seven link
   tuples carry a group each: `web` and `evidence` open, `pdf` and `excel` download; the page-language
   web report is marked primary; and no tuple lacks a group, so an eighth link cannot go ungrouped.
3. `test_the_group_headings_name_an_affordance_and_no_figure` — the two new keys exist in both languages
   and neither language's wording contains a digit, a per-cent sign, or a currency mark: a heading that
   starts carrying a figure has left `RRA-010`.

The existing three tests in that file are unchanged: the links are still absent from the initial HTML,
still exactly seven, still built only after `bundle_complete`.

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
