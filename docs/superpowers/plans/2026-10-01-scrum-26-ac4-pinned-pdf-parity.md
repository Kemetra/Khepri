# SCRUM-26: acceptance criterion 4, PDF parity in the pinned image

> ## STATUS: RUN ON 2026-10-01, `main` AT `72aa6d8`. EVERY SLICE IS CONFIRMED IN BOTH LANGUAGES
>
> SCRUM-26 acceptance criterion 4 asks for Arabic and English parity on the rendered PDF, in the
> pinned image, for every item changed. Three items changed: A11 (#633), the in-key half of A4
> (#634) and A9(a) (#635). Each one shows on the pinned renders in both languages. This document
> records what was exercised. It changes no authority and proposes no fix. The open owner
> readings, A3b, A4(b) and A9(b), are listed in
> [`2026-09-30-scrum-26-report-follow-ups.md`](2026-09-30-scrum-26-report-follow-ups.md).

## Method

This is the method of the SCRUM-21 re-run
([`2026-09-30-scrum-21-u1-acceptance-rerun.md`](2026-09-30-scrum-21-u1-acceptance-rerun.md)),
narrowed to the rendered report.

- **Pinned image.** `khepri-runtime:staging` was built from a `git archive` of `72aa6d8` (image
  `sha256:b23e703f…`, label `khepri.commit=72aa6d8`). Every PDF below was rendered only by a worker
  in that image, running `python -m khepri.local.cli work` against the host stack through
  `host.docker.internal`. Both PDFs report `Skia/PDF m149` as their producer.
- **Stack.** The local Postgres and MinIO containers on Docker Desktop were used, with
  `alembic upgrade head` applied from `72aa6d8`. #631 did not block this run, because this machine
  still holds the MinIO image. A clean machine cannot repeat it as committed.
- **Request.** The real beta API was driven in-process (`build_web_app` over the live stack), the
  same way `tests/test_local_journey.py` drives it: redeem, consent, upload, profile, facts,
  report. The file was `tests/rra_printed_support.retail_csv()` (160 rows, seed 21), the SCRUM-21
  file shape, with `tests.rra003_contract_fixtures.profile_payload()`. The job finished as
  `succeeded` with `narrative_state: included`. Both PDFs have 105 pages.
- **Reading the PDFs.** Text was extracted with `pypdfium2` and pages were captured at 1.4×.
  Arabic PDF text comes back in visual order, so every Arabic verdict was also read from a
  capture. The Arabic web report was string-matched as a second source.

## Results

| Item | English PDF | Arabic PDF | Result |
|---|---|---|---|
| **A11**: breakdown dates on one line | 275 whole ISO dates, no `YYYY-MM-` fragment without its day | 275 whole ISO dates, no fragment. Page 2 capture: one line each | **Pass** |
| **A4** (in-key half): no single-period claim | Page 6, Period comparison: the new `prior_window_absent` sentence is printed, and "covers a single period" appears on no page | Page 6 capture: the new sentence is printed. The Arabic web report has the new sentence and not the old one | **Pass** |
| **A9(a)**: whole-file facts by governed names | Page 11: five sentences, e.g. "Units sold: 836, as recorded in the file.", and no "The recorded …" | Page 11 capture: five sentences with Arabic measure names, e.g. "الوحدات المبيعة: 836، وفق ما سُجّل في الملف.", and no Latin word on the page | **Pass** |

Captures, in [`2026-10-01-scrum-26-ac4-captures/`](2026-10-01-scrum-26-ac4-captures/):
`a11-ar-pdf-page2-dates-one-line.png`, `a4-en-pdf-page6-comparison.png`,
`a4-ar-pdf-page6-comparison.png`, `a9-en-pdf-page11-commentary.png`,
`a9-ar-pdf-page11-commentary.png`.

## Observations, not findings

- **Latin codes in the Arabic PDF are in the evidence appendix only.** `revenue` and `units` occur
  on pages 13–14, in the calculation evidence's input and metric code columns. Those are governed
  codes, the same ones A2 keeps whole. They are not in the commentary or the sections.
- **A9(b) is visible, as expected.** The Arabic commentary quotes `23520.06` and `836` in Latin
  digits without grouping, while the Arabic tables print `٢٣٬٥٢٠٫٠٦`. That is the open owner
  reading, not a defect of #635.
- **A4(b) is visible, as expected.** The Period comparison section prints the coverage refusal
  and the `prior_window_absent` sentence side by side, and neither names its basis (period over
  period, or year over year). The sentence is now true. Naming the basis is the open RRA-009
  reading.
