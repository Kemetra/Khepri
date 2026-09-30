# SCRUM-21: U1 end-to-end UX/UI and report acceptance, re-run

> ## STATUS: RE-RUN ON 2026-09-30, `main` AT `5bc1565`. ACCEPTANCE IS THE OWNER'S CALL
>
> The three rendered-report defects from the first run are **not reproduced**. The Arabic PDF
> prints every column of its widest breakdown. Metric, kind and unit codes stay whole. The
> basket chart's labels sit in their own band below the bars. The journey, the in-place report
> and session isolation pass again. Two checks the first run did not exercise also pass: keyboard
> focus on `web/en`, `web/ar` and `evidence/en`, and reduced motion on `web/en`.
>
> What remains is the owner readings the first run left open, plus two newly recorded
> presentation findings, A11 and A12. #629 introduced neither. This document records what was
> exercised and what it showed. It changes no authority and proposes no fix.

The first run's record is
[`2026-09-29-scrum-21-u1-acceptance-evidence.md`](2026-09-29-scrum-21-u1-acceptance-evidence.md).
The fixes it asked for merged in PR #629 (SCRUM-25). Finding labels below are the first run's.

## Method

This follows the first run's method, with the differences listed under **Deviations**.

- **Checkout.** A detached worktree at `5bc1565`, with its own `uv` environment. The loaded
  package was confirmed as that worktree's `src/khepri`.
- **Stack.** `docker-compose.local.yml` from `5bc1565` in WSL (Postgres `17.11-alpine`, MinIO).
  `alembic upgrade head` reached `20260926_0034`. `khepri.local.app` was served on `:8010`.
- **Driver.** Playwright (Chromium) drove the real beta API from inside the browser context:
  redeem, consent, upload, profile, facts, report. Nothing was written to the database directly.
  Invitations were issued with `InvitationService.issue_invitation`, the operator action that
  RRA-001 keeps off HTTP.
- **Pinned renders.** `khepri-runtime:staging` was built from a `git archive` of `5bc1565`
  (image `sha256:4787c226…`, label `khepri.commit=5bc1565`). The normal, small and large jobs
  were rendered only by a worker in that image: `python -m khepri.local.cli work`, run with
  `--network host` against the same Postgres and MinIO. Inside the image, `khepri.local` imports
  and uses the same `launch_chromium` with `LAUNCH_ARGS ('--disable-dev-shm-usage',)`, and Python
  is 3.13.12. **Every PDF verdict below is read from the pinned renders.** A fourth job,
  `normal-local`, was rendered by the Windows-side worker for comparison only. Results for the
  journey, headers, isolation, layout, focus and motion come from the Playwright run against the
  `:8010` app. Causes cited from source come from reading `5bc1565`.
- **Files.** `tests/rra_printed_support.retail_csv` (seed 21) at 160 rows (normal), 1 row (small)
  and 40,000 rows (large). That is the SCRUM-25 file shape: date, revenue, units, paired
  invoices, category and branch. The profile body is `tests.rra003_contract_fixtures.profile_payload()`.
  It is not byte-identical to the first run's extracts, so page counts are not compared with
  that run (see A2b).
- **Reading the PDFs.** PyMuPDF, using text extraction with the media-box clip off, plus
  rasterized captures at 1.4×. PyMuPDF returns this PDF's Arabic text in visual order, split
  into glyph runs, so Arabic words cannot be string-matched. The Arabic checks therefore match
  figures, codes and Latin labels, and every Arabic finding was also read from a capture.
- **200% text** was applied as `html { font-size: 200% }` in a `bypass_csp` context, used for
  layout measurement only, as in the first run. This proves reflow of the root-relative text
  only. It does not show that all text scales: chart text is sized in the SVG (`.chart__label` is
  a fixed `10px`) and does not follow the root size.

### Deviations from the first run

- **MinIO was built from source.** The pinned `minio/minio:RELEASE.2025-09-07T16-13-09Z`
  cannot be obtained any more:
  - Docker Hub returns 404 for both `minio/minio` and `minio/mc` at repository level.
  - quay.io requires authentication.
  - dl.min.io returns 410 with the notice "The open-source MinIO Server, MinIO Client (mc) and
    MinIO KES projects are archived and no longer maintained".

  The first run worked from a cached image. For this run, the same release was built from its
  upstream tag (commit `07c3a42`) and substituted through a compose override kept outside the
  repository. The `mc ready` healthcheck became `curl …/minio/health/live`, because `mc` is
  equally unobtainable. Storage is not under test here, and every upload returned `201`.
  **Consequence outside SCRUM-21:** neither `docker-compose.local.yml` nor
  `docker-compose.staging.yml` can be started from a clean machine as committed. That is an
  owner decision for its own issue, not part of this Verification item.
- **No `host.docker.internal`.** The pinned worker reached the stack over the host network, which
  WSL's mirrored networking provides.
- **The stack stopped once, after the renders.** The WSL distribution idled out when its last
  session ended, as the compose file's own comment warns. Postgres logged a clean shutdown at
  18:19 UTC. Every job had finished by 18:14, so no render was affected. A later browser check was
  repeated after the stack came back, with a long-lived WSL process holding it up.

## Coverage

| SCRUM-21 case | How exercised | Result |
|---|---|---|
| Normal dataset | 160 rows through the whole pipeline | **Pass.** `succeeded`; all 7 surfaces served |
| Small / insufficient | 1 row | **Pass.** `succeeded`; PDFs of 25 pages (EN) and 24 (AR) |
| Invalid input | PNG bytes as `text/csv`; a header-only CSV | **Pass.** Both `400`, "Upload content is invalid or unsupported." |
| Partial / caveated | Normal run | Shown. **A5** unchanged |
| Analytical refusal | Normal run | Shown in the refused-results region and index. **A4** and **A6** unchanged |
| Large dataset / display sampling | 40,000 rows | **Pass.** `succeeded`. As in the first run, **no** display sampling was reached: page counts match the 160-row run exactly (105 / 106) |
| Permission / isolation | A second session and a request with no session, against the normal job | **Pass.** See §Isolation |
| Backend / processing failure | Not exercised | Still cannot be triggered without a code change |
| Arabic and English | Every surface, both languages | **Pass** for A1–A3. See **A11** and **A9** |
| Desktop and narrow | 1440 and 390, both languages | **Pass.** No page-level horizontal scroll |
| 200% text | Root font at 200%, 390, both languages | **Pass for reflow.** No page-level horizontal scroll. Chart text is fixed-size and was not measured |
| Keyboard / focus | 12 Tab stops each on `web/en`, `web/ar` and `evidence/en` at 1440 | **Pass.** Every stop had a visible focus indicator (outline or box-shadow). The stops were links, the focusable table scrollers, and the evidence drawers' `summary` |
| Reduced motion | `web/en` under `prefers-reduced-motion: reduce` | **Pass.** No element carries a transition or animation longer than 10 ms |
| Web report | Opened from the journey's report step | **Pass.** See §In place |
| Rendered PDFs | EN and AR, pinned image | **Pass** for A1, A2 and A3. See §Findings |

### In place (RRA-018 FR-240 to FR-253)

- **Headers.** The four web and evidence kinds are `inline`, with the CSP exactly
  `default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none';
  frame-ancestors 'none'; sandbox allow-same-origin`, plus `X-Frame-Options: DENY` and
  `Referrer-Policy: no-referrer`. PDF and Excel are `attachment` and carry none of those headers.
  File names are `khepri-report-{en,ar}.html`, `khepri-evidence-{en,ar}.html`,
  `khepri-report-{en,ar}.pdf` and `khepri-report.xlsx`.
- **Opening the report.** On `/beta/{en,ar}/report`, the primary card navigates the same tab to
  `surfaces/web/{lang}`. **No download fired.** The refused-results region is present.
- **Back.** Browser Back from the web report returns to `/beta/{lang}/report`, and **Delete
  content** is visible.
- **Evidence and return.** The first evidence link reaches
  `evidence/{lang}#evidence-section-overview`. FR-252's return link comes back to
  `web/{lang}`.

### Isolation

A second, consented session and a request with no session both asked for the normal job's
status, bundle, `web/en`, `evidence/ar`, `pdf/en` and `excel`:

- **Second session:** `404` with `application/json` on all six.
- **No session:** `401` with `application/json` on all six.

Neither served inline HTML or a `Content-Disposition`.

## Findings

### A1 to A3: not reproduced

- **A1, printed tables in Arabic. Fixed, by inspection.**
  - The Arabic PDF's three five-column breakdowns (by date, by category, by branch) all print
    whole, with every column inside the page. That covers page 2 and pages 3–6. SCRUM-25 measured
    three Arabic tables overflowing; these are those three.
  - This verdict rests on the captures. Two automated checks were run as well: no word lies
    outside any page, and every last-column figure appears in the text. **Neither can tell a
    clipped column from a whole one**, because that column is `3` in every row and Chromium does
    not write off-page glyphs. So neither is cited as evidence.
  - Captures: [a1-ar-pdf-page2-breakdown-fits.png](2026-09-30-scrum-21-rerun-captures/a1-ar-pdf-page2-breakdown-fits.png)
    and [a1-ar-pdf-pages3-6-breakdowns-fit.png](2026-09-30-scrum-21-rerun-captures/a1-ar-pdf-pages3-6-breakdowns-fit.png).
- **A2, codes in the evidence appendix. Fixed.**
  - Every `<code>` value in the evidence HTML was checked across all eight PDFs for a split
    across lines. Digests were excluded. The rest are 80 codes, including `value` and
    `monetary`, and none splits. The page-13 capture shows the metric, kind and unit columns
    whole.
  - What still wraps is the opaque references only: figure references (`cit_50b7…/value`),
    citation references and the three SHA-256 digests on the last page. PR #629 kept those
    wrappable as proposed, and the owner accepted that on 2026-09-29.
  - Capture: [a2-en-pdf-page13-codes-whole.png](2026-09-30-scrum-21-rerun-captures/a2-en-pdf-page13-codes-whole.png).
- **A3, basket chart labels. Fixed.**
  - The category labels sit in a band below the plot, clear of every bar.
  - The axis unit ("Share" / "نصيب") has its own row.
  - Seen on the English web report, and on the English (page 9) and Arabic (page 10) PDFs.
  - Captures: [a3-en-web-basket-labels.png](2026-09-30-scrum-21-rerun-captures/a3-en-web-basket-labels.png)
    and [a3-ar-pdf-page10-basket-labels.png](2026-09-30-scrum-21-rerun-captures/a3-ar-pdf-page10-basket-labels.png).

### Newly recorded. Neither is introduced by #629

- **A11: Arabic PDF breakdowns wrap their dates.** In the Arabic PDF's breakdown tables, each
  date row label wraps onto two lines. The English tables keep dates on one line.
  - **Predates #629.** The first run's own capture
    (`2026-09-29-scrum-21-captures/a1-ar-pdf-page2-clipped-column.png`) already shows `2026-` /
    `01-05`. On `5bc1565` the break falls at the last hyphen instead (`2026-01-` / `05`).
  - **Impact:** nothing is lost, but each date reads across two lines.
  - Visible in the A1 captures. This needs an owner reading: accept it, or open a follow-up under
    `RRA-006`.
- **A12: the line chart's end point and its label are cut at the chart's edge.** On the
  Concentration chart, the last tick label ("3") and its marker sit exactly on the canvas edge,
  and half of each is clipped. It happens at the start edge in Arabic and the end edge in
  English. The top marker is likewise halved at the top edge.
  - **Where:** the Arabic PDF (page 8), the English PDF (page 7) and the Arabic web report.
  - **Predates #629.** `charts.py` places the *n*-th point at `CHART_WIDTH × (index + 1) / n`,
    so the last point is at x = 640 on a 640-wide `viewBox`. The SVG's `overflow` is `hidden`.
    #629 changed only vertical geometry. The first run did not report this.
  - **Impact:** a reader loses half of the "3" and half of the last marker. No figure is lost:
    the section's table beneath states every value.
  - **Governing spec:** `RRA-015` owns chart geometry (§Scope, "axis and label geometry"). This
    needs an owner reading: accept it, or open a follow-up.
  - Captures: [a12-ar-pdf-page8-concentration-edge.png](2026-09-30-scrum-21-rerun-captures/a12-ar-pdf-page8-concentration-edge.png),
    [a12-en-pdf-page7-concentration-edge.png](2026-09-30-scrum-21-rerun-captures/a12-en-pdf-page7-concentration-edge.png)
    and [a12-ar-web-concentration-edge.png](2026-09-30-scrum-21-rerun-captures/a12-ar-web-concentration-edge.png).

### Owner readings still open, unchanged by #629 unless stated

- **A2b: page count, for this file.**
  - The normal and large files both print 105 pages in English and 106 in Arabic. The small file
    prints 25 and 24.
  - In English, the appendix starts on page 12, so the business report is pages 1 to 11.
  - The Arabic appendix start was not established from text (see Method).
  - The pinned and Windows-side renders match page for page (`Skia/PDF m149`, Chromium).
- **A3b: English qualifier in Arabic. Still present.** The Arabic chart and table show
  "Dairy (category)" and "نسبة عمليات البيع … — Dairy (category)". The qualifier is composed
  upstream, as recorded in the first run.
- **A4, A5, A6: not re-read in detail.** Their inputs are unchanged by #629: no template,
  wording or bundle change. The summary still counts "Answered with caveats" (A5).
- **A7: accepted as is** by the owner on 2026-09-29.
- **A8: raw JSON on a refused surface. Unchanged.** Every refusal above is `application/json`.
- **A9: commentary. Unchanged, with a newly noted Arabic aspect.** #629 did not touch the
  narrative. Besides the unformatted figures the first run noted ("23520.06"), the Arabic
  commentary names every measure by its English code: "القيمة المسجلة لـ revenue هي 23520.06",
  then `units`, `transactions`, `average order value`, `revenue by store`. It also prints Latin
  digits, while the rest of the Arabic report uses Arabic-Indic figures. The first run did not
  record this aspect.
  Capture: [a9-ar-pdf-page12-commentary.png](2026-09-30-scrum-21-rerun-captures/a9-ar-pdf-page12-commentary.png).
- **A10: stale comments. Unchanged.** `src/khepri/rra/journey/assets/report.js` and
  `src/khepri/rra/journey/templates/report.html.j2` still say that every surface is served as
  an attachment.

## What this run does not establish

- **Processing failure** and **display sampling** were not reached.
- **Nothing was recorded to the Loom runtime-evidence folder.** Only the nine captures linked
  above are in the repository.
- **No hosted environment was involved.** OPS1 is deferred.
- The keyboard check samples 12 Tab stops per surface. It is not a complete traversal.

## Recommendation for the owner

- **A1 to A3**, the condition the owner set on 2026-09-29, are met on `5bc1565` in the pinned
  image.
- **Accepting SCRUM-21** now turns on the open readings: A2b, A3b, A4, A5, A6, A8 and A9, plus
  the newly recorded A11 and A12. None was introduced by #629. Each can be accepted as governed,
  or split into its own slice, without blocking the others.
- **Separately:** the unobtainable MinIO image makes both compose stacks unstartable from a clean
  machine. It needs its own issue.
