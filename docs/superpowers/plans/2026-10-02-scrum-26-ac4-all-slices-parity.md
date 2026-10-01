# SCRUM-26 acceptance criterion 4: PDF parity in the pinned image for A4(b), A3b and A9(b)

> Evidence record. SCRUM-26 AC4 requires Arabic and English parity on the rendered PDF, in the
> pinned image, for every item changed. The first record
> ([`2026-10-01-scrum-26-ac4-pinned-pdf-parity.md`](2026-10-01-scrum-26-ac4-pinned-pdf-parity.md))
> covered A11, the in-key half of A4, and A9(a). This one covers the three slices that `#637`
> authorized: A4(b) (#639), A3b (#640) and A9(b) (#641). It changes no authority and proposes no
> fix.

## Method

- **Pinned image.** `khepri-runtime` was built in WSL with `docker build --platform linux/amd64`
  from a `git archive` of tree `3952fab`. That tree is exactly the tree of `main` at `11d1c20`
  (`git rev-parse 11d1c20^{tree}`). Image ID: `sha256:5369d833…`, label
  `khepri.tree=3952fab…`. Inside the image: Python 3.13.12, and `khepri` imported from
  `/opt/khepri/src`.
- **Render.** Every PDF was printed only by the image's own Chromium (`launch_chromium`), through
  `PdfReportRenderer.render_pdf`. Every PDF reports `Skia/PDF m149` as its producer.
- **Pipeline.** The real pipeline ran in-process inside the image:
  - `build_fact_package`;
  - `NarrativeRequest.of`, then `DeterministicNarrator.draft`, then `narrative.validate`;
  - `ReportBundle.of` with the narrative included.

  The test fixtures came from the same archive, mounted read-only.
- **Change of method.** Unlike the first record, this run has no Postgres, MinIO or beta-API round
  trip. Storage and the journey are not under test here. What is under test is what the bundle,
  the narrative and the printed templates write, and all of that ran in the image.
- **Recorded versions.** `rra006.bundle.v9` and `rra005.deterministic.v4`. Every case finished
  with `narrative_state: included`.
- **Reading.** English text was extracted with `pypdf`. Arabic text extracts in visual order as
  glyph runs, so every Arabic verdict below was read from a capture at 1.4×.

| Case | File | EN pages | AR pages |
|---|---|---|---|
| `retail` | `tests/rra_printed_support.retail_csv()` (160 rows, seed 21), the SCRUM-21 shape | 106 | 106 |
| `shared` | a product `Water` and a category `Water` sharing one value (`tests/test_rra006_dimension_token.py`) | 102 | 99 |
| `split` | four days, no coverage manifest: previous period refused for coverage, the same period last year for `prior_window_absent` (`tests/test_rra009_refusal_basis.py`) | 31 | 27 |

## Results

| Item | English PDF | Arabic PDF | Result |
|---|---|---|---|
| **A4(b)**: each basis named by its own cause | `split` p5: the panel opens "Against the previous period: Comparison with an earlier period — not available. Your file covers both periods, but not in the same way…" and continues "Against the same period last year: … Your file does not include the earlier period…". Each result sentence names its basis | `split` p4 capture: the same two panel sentences, led by "مقابل الفترة السابقة:" and "مقابل الفترة نفسها من العام الماضي:", with the three result sentences each led by their basis | **Pass** |
| **A3b**: a shared value told apart, with the qualifier in the page's language | `shared` p9: "Water (product)" and "Water (category)" in the table and on the chart axis | `shared` p8 capture: "Water (منتج)" and "Water (فئة)" in the table and under each bar. No "(product)" or "(category)" in the Arabic PDF | **Pass** |
| **A9(b)**: commentary figures in the tables' form | `retail` p11: "Revenue: 23,520.06" (grouped). The bare `23520.06` is on no page | `retail` p11 capture: "الإيرادات: ٢٣٬٥٢٠٫٠٦", "٨٣٦", "٢٩٤٫٠٠", "٢٨٫١٣", all Arabic-Indic digits with the Arabic separators | **Pass** |
| **No regression** of A11 and A4 (in-key) | `retail`: no `YYYY-MM-` date fragment, and no "covers a single period" | `retail`: no date fragment | **Pass** |

Captures, in [`2026-10-02-scrum-26-ac4-captures/`](2026-10-02-scrum-26-ac4-captures/):
`a4b-en-pdf-page5-comparison.png`, `a4b-ar-pdf-page4-comparison.png`,
`a3b-en-pdf-page9-basket.png`, `a3b-ar-pdf-page8-basket.png`,
`a9b-en-pdf-page11-commentary.png`, `a9b-ar-pdf-page11-commentary.png`.

## With this record

All four SCRUM-26 acceptance criteria now have repository evidence:

1. Each finding is mapped to its governing specification: #633–#635 and #637.
2. The amendments were proposed to the owner and merged: #637.
3. Bounded, spec-linked slices each have their own PR: #633, #634, #635, #639, #640, #641.
4. Pinned-image PDF parity: #636 and this record.
