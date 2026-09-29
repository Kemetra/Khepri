# SCRUM-21: U1 end-to-end UX/UI and report acceptance, first run

> ## STATUS: NOT YET ACCEPTED. First run on 2026-09-29, `main` at `a2bbf40`
>
> The journey, the in-place report and session isolation pass. **The rendered deliverables
> do not pass yet.** The Arabic PDF clips a column of figures. Identifiers in the PDF evidence
> appendix break mid-word. One chart draws its labels over its own bars. All three fall under
> SCRUM-21's own presentation-coverage list: "page breaks, long tables, headings and chart
> sizing". Several further findings need an owner reading, not a fix.
>
> Acceptance is the owner's call. This document records what was exercised and what it showed.
> It changes no authority, and it proposes no fix inside SCRUM-21. Any fix is a separate
> spec-linked slice.

## Method

- **Stack.** `docker-compose.local.yml` (Postgres, MinIO). `uv run alembic upgrade head`.
  `khepri.local.app` served on `:8010`. Reports were processed with `python -m khepri.local.cli work`.
- **Driver.** Playwright (Chromium) drove the real beta API from inside the browser context: redeem,
  consent, upload, profile, facts, report. The pages below were therefore reached with the session
  cookie a user would hold. Nothing was written to the database directly.
- **PDFs in the pinned image.** The PDFs were rendered a second time by a worker running inside
  `khepri-runtime:staging`, built from `a2bbf40`. It reached the same Postgres and MinIO through
  `host.docker.internal`. Both renders report `Skia/PDF m149` and have identical page counts. The
  findings below were read from the pinned render's pages.
- **Files.** Three extracts in the `date,revenue,units,invoice_no,category,branch` shape of
  `tests/test_local_journey.py`, with seeded random values: 160 rows (normal), 1 row (small), and
  40,000 rows (large). The normal and large extracts both span 2026-01-05 to 2026-02-28.
- **200% text** was applied with `html { font-size: 200% }`, as `test_rra016_journey_composition.py`
  does. On the report surfaces, the injection needed a browser context with `bypass_csp`, because
  FR-241's policy correctly refuses an injected style. That context was used for layout
  measurement only. Every other request ran under the real policy.

## Coverage

| SCRUM-21 case | How exercised | Result |
|---|---|---|
| Normal dataset | 160 rows through the whole pipeline | **Pass.** `succeeded`; all 7 surfaces served |
| Small / insufficient | 1 row | **Pass.** `succeeded`; Period comparison and Growth refused (`prior_window_absent`), stated in 2 refusal panels |
| Invalid input | PNG bytes sent as `text/csv`; a header-only CSV | **Pass.** Both refused with `400` and the governed "Upload content is invalid or unsupported." The journey's rendering of the error is covered by the RRA-016 tests |
| Partial / caveated | Normal run | **Pass**, with finding **A5** |
| Analytical refusal | Normal run: Period comparison and Growth refused (`coverage_structurally_incompatible`); 9 results refused individually | Shown. See **A4** and **A6** |
| Large dataset / display sampling | 40,000 rows | **Pass.** `succeeded` in 6.5 s end to end. The breakdowns are bounded by distinct dates, not by rows, so this run reached **no** display sampling: page counts match the 160-row run exactly |
| Permission / isolation | A second session and a session-less request against the first session's job | **Pass.** See §Isolation |
| Backend / processing failure | Not exercised | It cannot be triggered without a code change, so it was not built in. The journey's failure state is covered by `test_rra016_journey_composition.py` |
| Arabic and English | Every surface, both languages | Findings **A1** and **A3** |
| Desktop and narrow | 1440 and 390 | **Pass on screen.** No page-level horizontal scroll in either language; wide tables scroll inside `.scroller` |
| 200% text | 390, both languages, the whole report and the refused-results region | **Pass.** No page-level horizontal scroll, and nothing clipped in the refused-results region |
| Keyboard / focus, reduced motion | **Journey:** `test_rra016_journey_composition.py`, `test_rra010_journey_focus.py`. **Report:** not exercised in this run | Report surfaces open |
| Web report | Opened from the journey's report step | **Pass.** See §In place |
| Rendered PDFs | EN and AR, local and pinned image | **Fail.** **A1**, **A2**, **A3** |

### In place (RRA-018 FR-240 to FR-253, observed)

- **Headers on three runs (normal, small, large).** The four web and evidence kinds are `inline`,
  with CSP exactly `default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action
  'none'; frame-ancestors 'none'; sandbox allow-same-origin`, plus `X-Frame-Options: DENY` and
  `Referrer-Policy: no-referrer`. PDF and Excel are `attachment` and carry none of those headers.
  File names are distinct per language: `khepri-report-en.html` and `khepri-report-ar.html`.
- **Opening the report.** Clicking the primary card on `/beta/{en,ar}/report` navigates the same tab
  to the web report. **No download fires.** The refused-results region is present in both
  languages.
- **Evidence links.** A section's evidence link reaches `…/evidence/en#evidence-section-overview`
  with the session ("Technical evidence"), and the return link comes back to the report.
- **Back.** Browser Back returns to `/beta/{lang}/report`. The step repopulates from `resume()`,
  and **Delete content** is still visible.

### Isolation

A second, consented session and a request with no session both asked for the first session's
report job, its bundle, `web/en`, `evidence/ar`, `pdf/en` and `excel`:

- **Second session:** `404` with `application/json` on all six.
- **No session:** `401` on all six.

Neither case served inline HTML or a `Content-Disposition`. Opening the owner's `web/en` in the
second session's browser shows only the JSON refusal (**A8**).

## Findings

**Defects in the rendered deliverables.** All three predate `#627`: the files involved are not in
its diff, apart from A1's print stylesheet, which `#627` touched only to add the refused-results
rule.

- **A1: the Arabic PDF clips the widest breakdown table.** On screen the table scrolls inside
  `.scroller`. In print, `report.print.css:68` sets `.scroller { overflow: visible }`. Its own
  comment says this exists so that no column past the edge is clipped "silently, which is the worst
  way for a figure to go missing". In RTL the overflow spills past the page's *left* edge instead,
  which defeats the rule's stated purpose.
  - **What is lost:** on the Overview breakdown, the fifth and last column ("Units sold (rows
    counted)", "الوحدات المبيعة (عدد الصفوف المحتسبة)") has its header cut off and its values
    missing.
  - **Measurement:** the English table fits. On the web HTML at a 794px viewport, the Arabic tables
    start at −30 to −51px.
  - **The printed Arabic report loses data.**
- **A2: identifiers in the PDF evidence appendix break mid-word.** For example `valu e`,
  `monet ary`, `cit_c74d30a8cd6 9/value/1` and `concentration_curv e`. The appendix's narrow
  columns wrap codes at arbitrary characters.
- **A3: the Basket structure chart draws its category labels over the bottoms of its bars.** The
  labels are clipped ("Snacks (category)" loses its descenders), and the axis label
  "Share" / "نصيب" collides with the first bar. Seen on the English web report and in both PDFs.

**Owner readings needed before a fix direction exists.**

- **A2b: the evidence appendix is most of the printed document.** The English PDF has 97 pages,
  and the business report is pages 1–12. The Arabic PDF has 87. Even the 1-row file prints 24
  pages.
  - **The drawers print open.** Each figure prints its drawer: version, definition, and three
    "Not stated" lines. That leaves about four figures to a page.
  - **This looks intended.** `report.print.css` keeps "a printed drawer" on the same page as its
    figure (`.evidence-figure-row { break-after: avoid }`).
  - **The question** is whether the page count is acceptable for the delivered PDF.
- **A3b: the Arabic report prints an English qualifier.** The Arabic chart and table show
  "Snacks (category)" and "نسبة عمليات البيع … — Snacks (category)". The qualifier is composed
  upstream of rendering, as `f"{label} ({dimension})"` with the untranslated semantic key
  (`src/khepri/rra/analysis/basket.py:248`). RRA-018 bars bundle and package changes, so the fix
  belongs to whichever specification governs basket labels, not to the renderer.
- **A4: two refused comparison bases read as one contradiction.** The Period comparison section
  carries two different refusals:
  - `period_over_period:coverage_structurally_incompatible`: "Your file covers both periods, but
    not in the same way".
  - `year_over_year:prior_window_absent`: "Your file covers a single period, so there is no
    earlier period inside it".

  Each is true of its own basis. But the prose never names the basis, and the second sentence's
  remedy offers "the months immediately before", which is the basis the first sentence refuses.
  To a reader of the same page they contradict each other. This is a wording question for the
  specification that owns caveat prose.

**Inconsistencies surfaced by the new index.**

- **A5: the summary counts a caveat that no badge shows.** The header reads "Answered 2 · Answered
  with caveats 1 · Refused 2". Every section badge, and every entry in the FR-245 index, says
  "Answered" or "Refused", so a reader cannot find the caveated section. It is Overview, whose
  caveat is "No chart is shown for this section." The refused Period comparison also carries
  section caveats, but refused sections are counted as refused.
  - **Cause:** the summary counts sections that carry `caveats`
    (`report.html.j2:58-63`), while the badge shows `state` (`status_badge`).
  - **Owner reading:** does a chart-omission note count as a caveat in the summary?

**Owner judgment. Each outcome is governed as shipped.**

- **A6: the reason sentence names the measure alone.** The refused-results region reads "Revenue
  is not shown — the file does not contain Sales channel.", above the name "Revenue — Sales
  channel". It appears on a page whose Overview states revenue. FR-246 qualified the *name* to
  avoid exactly this reading. The *sentence* comes from `caveat_prose`, and RRA-018 §Exclusions
  forbids new reason prose, so it cannot change inside RRA-018.
- **A7: same-tab navigation.** The report replaces the journey page in the same tab. The report
  has no link back to the journey, but Back restores it with the session live (§In place).
  RRA-016 FR-226 and RRA-018's rationale keep every journey destination unchanged, so a new tab
  or a return link would each need its own slice.
  - **Recommendation:** accept as is. Back works, and the stored report cannot know the journey's
    address without becoming session-bound.
- **A8: a refused surface renders as raw JSON in the tab.** A link opened in another session, or
  after deletion or expiry, shows
  `{"detail":"No report artifact is available for this session."}`. This was true before `#627`.
  What changed is how often a reader lands on it, because the report now opens as a page. RRA-018 §Exclusions bars
  changing the report API's refusal model.

**Minor, and adjacent.**

- **A9: the commentary restates unformatted figures.** It reads "The recorded revenue is
  17084.23.", where the table shows `17,084.23`, and "The recorded units is 743." has an agreement
  error.
- **A10: two stale comments.** `src/khepri/rra/journey/assets/report.js:21` and the Jinja
  comment at `src/khepri/rra/journey/templates/report.html.j2:12` both say that every surface is
  served as an attachment, citing `report_api.py:562`. That has been false since `#627`. RRA-018
  §Exclusions bars journey template changes, so this is a comment-only fix under RRA-016.

## Captures

The pages behind A1–A3, kept so a later fix can be compared against them. The PDF pages come
from the pinned-image render, rasterized at 1.4×.

| Finding | Capture |
|---|---|
| A1: Arabic PDF, page 2, last breakdown column clipped | [a1-ar-pdf-page2-clipped-column.png](2026-09-29-scrum-21-captures/a1-ar-pdf-page2-clipped-column.png) |
| A2: English PDF, page 16, identifiers wrapped mid-word | [a2-en-pdf-page16-identifier-wrap.png](2026-09-29-scrum-21-captures/a2-en-pdf-page16-identifier-wrap.png) |
| A3: English web report, basket chart labels over bars | [a3-en-web-basket-labels.png](2026-09-29-scrum-21-captures/a3-en-web-basket-labels.png) |
| A3 and A3b: Arabic PDF, page 10, the same chart, with the English qualifier | [a3-ar-pdf-page10-basket-labels.png](2026-09-29-scrum-21-captures/a3-ar-pdf-page10-basket-labels.png) |

## What this run does not establish

- **Processing failure** and **display sampling** were not reached (see §Coverage).
- **Keyboard, focus and reduced motion on the report surfaces** were not exercised.
- **Nothing was recorded to the Loom runtime-evidence folder.** Only the four captures above are
  in the repository. The full PDFs and the other screenshots were not kept.
- **No hosted environment was involved.** OPS1 is deferred.

## Recommendation

- **Keep SCRUM-21 In Progress.** Accepting now would accept A1, a column of figures missing from
  the Arabic PDF.
- **Smallest unblocker:** a spec-linked fix slice for **A1 to A3**:
  - A1: RTL table overflow on paper;
  - A2: identifier wrapping in the evidence appendix;
  - A3: the basket chart's label band.

  The files are `report.print.css`, the evidence template and `charts.py`/`_chart.svg.j2`. Which
  specification governs each is **not yet confirmed**: RRA-012, RRA-013 and RRA-015 reference
  them. Settle that against `registry.yaml` and each spec's §Scope before the slice is sized.
- **A2b, A3b, A4 and A5** each need an owner reading first.
- **A6 to A8:** accept as governed, or open a spec amendment for them.
- **After the fix:** re-run this document's method and replace the status banner.
