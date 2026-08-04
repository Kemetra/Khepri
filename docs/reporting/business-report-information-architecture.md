# Business-report information architecture

**Status:** draft for owner approval. Docs only.

Companion to `presentation-visibility-matrix.md`, which classifies *fields*. This
document defines *structure*: what the customer-facing report is, in what order,
on each of the three surfaces — and where the audit layer attaches.

---

## B.0 The governing principle

> **Lead with the finding. The number is evidence for the finding, not the
> finding itself.**

The current report is ordered by *mechanism*: sections in bundle order, each a
table of figures, then caveats, then citations, then provenance. That is the
order in which Khepri computed things.

A business report is ordered by *decision relevance*: what happened, why, who
drove it, what it means, what is missing. That is the order in which a retail
owner reads.

Every rule below follows from that inversion.

---

## B.1 Two layers — always generated, separately delivered

| Layer | Purpose | Audience | Delivery |
|---|---|---|---|
| **Business report** | The deliverable. Findings, figures, charts, limitations. | The customer, their staff, their bank | **Always** |
| **Audit evidence** | The defensibility mechanism. Identifiers, citations, provenance. | An auditor, a sceptical CFO, a dispute | **On request** |

**Owner decision, 2026-08-04: the business report is the product; the audit
evidence is optional to the customer.**

The word "optional" is load-bearing and applies to **delivery only**. The
distinction is not stylistic — getting it the other way round breaks the build.

### Why the audit layer is always *generated*

`REQUIRED_SURFACES = (web, pdf, excel)` (`bundle.py:89`) is compared for exact
equality in six places — `bundle.py:1222`, `pipeline.py:156`, `pipeline.py:345`,
`reports.py:253`, `delivery_persistence.py:349`, `benchmark_trial.py:164`. A
bundle that produces fewer than three surfaces returns
`REASON_MISSING_SURFACE` and becomes an **incomplete bundle**
(`bundle.py:1222-1223`) — meaning no report is delivered at all, not a smaller
report.

There is a second and stronger reason. `surface_digest`
(`delivery_persistence.py:242-250`) content-addresses what each surface
*presented*. If audit content were generated conditionally, two runs of the same
input would produce different digests depending on a customer preference — and
"re-running the same input reproduces the same bundle identity" is the claim the
product is sold on. Conditional generation would make reproducibility a function
of a preference rather than of the data.

**So the audit layer is generated for every report, always, unconditionally.**

### Why it is *delivered* on request

Generation and delivery are already separate stages.
`delivery_persistence.py:239` reads surfaces back **per surface**, each with its
own stored digest:

```python
return tuple(found[surface] for surface in REQUIRED_SURFACES if surface in found)
```

The `if surface in found` guard means the delivery layer already tolerates
reading a subset. So withholding the audit layer from a customer download is a
delivery-time filter, not a generation-time branch. **No governance change, no
reconcile change, no change to the bundle contract.**

### What the customer sees

| Surface | Default delivery | On request |
|---|---|---|
| **HTML** | Business report page | "Technical evidence" — a separate page, linked from the colophon |
| **PDF** | Business PDF, no appendix | Appendix PDF (or the combined file) |
| **Excel** | Business worksheets 1–7 | Full workbook including sheets 8–10 |

The business report names its reference and points to the evidence, once, in the
colophon — and carries no identifier anywhere else:

> **Report reference 4A7C-2F91 · version 2**
> Full calculation evidence and data lineage available on request.

That pointer is deliberate. It keeps the defensibility claim visible to the
reader — a report that never mentions its own evidence cannot be forwarded to an
auditor by someone who does not know the evidence exists — while putting no
figure id, digest, or reason code in the body.

---

## B.2 HTML

```
Business report  (report.html)
├── Header
│   ├── Report title + client name + period covered
│   └── Governed disclosure                    ← verbatim, immutable
├── 1. Summary
│   ├── Lead finding (prose, 1–3 sentences)
│   ├── Hero figure + delta
│   └── KPI row (≤ 4 stat tiles)
├── 2. Sales performance
│   ├── Finding sentence
│   ├── Chart (line — trend)
│   └── Supporting figures (business names, no identifiers)
├── 3. Period comparison
│   ├── Finding sentence
│   └── Chart (grouped bar)
├── 4. Growth drivers
│   ├── Finding sentence
│   └── Chart (grouped bar — price / volume effects)
├── 5. Concentration
│   ├── Finding sentence
│   └── Chart (line — cumulative share curve)     ← RRA-008 requires this kind
├── 6. Basket analysis
│   ├── Finding sentence
│   └── Chart (bar)
├── 7. What this review does not cover           ← §D refusals + caveats, in prose
├── Commentary                                   ← narrative passages, no cited ids
└── Colophon
    ├── "Report reference 4A7C-2F91 · version 2"
    └── "Full calculation evidence and data lineage available on request."
        (link → Technical Evidence, when the customer has requested it)

Technical Evidence  (report.evidence.html)          ← generated always, served on request
├── How to read this page
├── Figures table        ← figure_id, metric, kind, unit_kind, value, citation_id
├── Section states       ← section_id, state, raw reason code
├── Caveat codes         ← raw codes beside their customer prose
├── Citations            ← citation_id → fact
├── Commentary citations ← passage → cited_fact_ids
└── Provenance           ← full BundleIdentity, bundle_id, surface versions
```

A refused section keeps its numbered place in the business report **only if its
refusal is worth a heading**; otherwise it appears under §7. Recommended: refused
sections appear under §7 and the numbered list contracts, so a customer does not
read six headings of which three are apologies. This is a design choice the owner
should confirm — the alternative (keep the heading, put the prose under it) is
also defensible and preserves a 1:1 map to the bundle's sections.

---

## B.3 PDF

The PDF reuses the HTML structure — `pdf.py:193` already renders through the
shared `build_context`, and `report.pdf.html.j2` extends the web template. So:

```
Page 1        Cover — title, client, period, disclosure, report reference
Pages 2–n     Business report §1–§7   (same content as HTML, paginated)
              ── page break ──                    ← appendix omitted by default
Appendix A    Figures and citations                 (delivered on request)
Appendix B    Section states and reason codes       (delivered on request)
Appendix C    Provenance and versions               (delivered on request)
```

The appendix begins on a fresh page with its own running header. Because the
default delivery omits it entirely, the business PDF ends at the colophon and is
a complete document on its own — a customer who prints and forwards it is not
forwarding a truncated file.

**No forked template.** The appendix is a `{% block appendix %}` in the shared
template. This preserves the DEC-005 single-engine property: Arabic/English
parity, the disclosure, and the figure set stay correct in one place.

**Two printed artifacts, one generation pass.** The appendix block is rendered
whether or not it is delivered, because the surface content must still reconcile
(see §B.1). Which file the customer downloads is a delivery-layer choice:

| Requested | Delivered |
|---|---|
| Business report (default) | Pages 1–n, appendix suppressed |
| With evidence | The full document, appendix included |

---

## B.4 Excel

Worksheet order **is** the information architecture in a workbook, because it is
what a reader sees on opening. Business sheets first, in reading order; mechanism
sheets last.

| # | Worksheet | Tier | Delivered | Contents |
|---|---|---|---|---|
| 1 | Executive Summary | B | always | Lead finding, hero figure, KPI block, period covered, disclosure |
| 2 | Sales Performance | B | always | Revenue / units / transactions / average sale by period |
| 3 | Period Comparison | B | always | Current vs prior, absolute and percentage |
| 4 | Growth Drivers | B | always | Price effect, volume effect, total change |
| 5 | Product & Category Performance | B | always | Ranked contribution |
| 6 | Basket Analysis | B | always | Items per sale, attach rate |
| 7 | Data Limitations | B | always | Every refusal and caveat in customer prose (§D) |
| 8 | Chart Data | A | always¹ | Existing chartdata sheet — the one numeric write path (`APP-013`) |
| 9 | Audit Trail | A | on request | section_id, state, raw reason, figure_id, metric, kind, unit_kind, citation_id |
| 10 | Provenance | A | on request | Full BundleIdentity, bundle_id, surface versions |

¹ Sheet 8 holds the chart series addresses the embedded charts read, and it must
ship with the business workbook or the native charts break. `_series_range`
(`excel.py:656-665`) addresses the chartdata sheet **by name**, so a chart whose
series points at a removed sheet renders empty. It carries no authoritative figure
and no citation (`excel.py:56-60`), so it is Audit-tier by classification but
always-delivered by necessity. Recommended treatment: **hidden**
(`sheet.hide()`) — present for the charts, absent from the sheet tabs.

Business sheets carry **business column names**. No sheet in 1–7 contains a
`figure_id`, `citation_id`, raw `metric`, `kind`, or `unit_kind` column.

**Two workbooks, one generation pass.** The default download carries sheets 1–8;
the on-request download carries all ten. Both are written from the same bundle in
the same pass, so no figure can differ between them.

### The table above is per language, and the real workbook is bilingual

`_write_workbook` (`excel.py:341-354`) loops `for language in LANGUAGES` and
writes every sheet twice — `_REPORT_SHEET`, `_CITATION_SHEET` and the section
sheets are all per-language dictionaries (`excel.py:147-148`). Only `Provenance`
is written once, in English (`excel.py:688`), because it holds nothing
translatable.

So the delivered workbook is roughly **15 sheets, not 10**: seven business sheets
× 2 languages, a hidden chartdata sheet × 2, an Audit Trail × 2, and one shared
Provenance sheet.

**The golden sample shows the English half only.** That is a deliberate
simplification to keep the sample readable, and it is the one place the sample
diverges from the delivered artifact. Two naming options for the implementation
slice, and the owner should pick:

| Option | Sheet names | Trade-off |
|---|---|---|
| **(a)** Suffix, as today | `Executive Summary (English)` / `الملخص التنفيذي (العربية)` | Consistent with the current `_REPORT_SHEET` convention; 15 tabs is a lot to scan |
| **(b)** Two workbooks | One file per language, 8 tabs each | Cleaner for the reader; doubles the delivered files and needs a delivery-layer change |

**(a) is recommended** — it changes no delivery contract, and a bilingual client
opening one file is the current behaviour customers have already seen. Revisit if
15 tabs tests badly.

Sheet 5 (Product & Category) is listed because the owner asked for it. **Flagged
dependency:** the current bundle's section set is
`overview / comparison / concentration / growth / basket`. There is no
product-or-category performance section. Sheet 5 is therefore either (a) a
re-presentation of the concentration family's ranked buckets under a business
name, or (b) genuinely new analysis requiring an `RRA-008` family. **(a) is
recommended** — it needs no new governed analysis, and the concentration family
already ranks buckets by contribution. The golden sample uses (a).

Sheet 7 is where the reconcile constraint lands: `bundle.py:1324` requires the
caveat set to match exactly, so this sheet must be complete, not curated.

---

## B.5 Naming — business names for governed metrics

The matrix (§A.1) established there is **no existing translation path for
`metric`**. This is the table that has to exist. Illustrative, not exhaustive —
the implementation slice derives the full key set from the governed metric
vocabulary.

| Governed metric | English business name | Arabic business name |
|---|---|---|
| `revenue` | Revenue | الإيرادات |
| `units` | Units sold | الوحدات المبيعة |
| `transactions` | Number of sales | عدد المبيعات |
| `average_transaction_value` | Average sale value | متوسط قيمة البيع |
| `growth_revenue_change` | Total revenue change | إجمالي تغير الإيرادات |
| `growth_price_effect` | Effect of price changes | أثر تغير الأسعار |
| `growth_volume_effect` | Effect of volume changes | أثر تغير الكميات |
| `items_per_transaction` | Items per sale | عدد الأصناف لكل بيع |
| `attach_rate` | Attach rate | معدل الإضافة |
| `concentration_*` | Share of sales | نصيب من المبيعات |

Arabic column requires owner review — `RRA-005` demands genuine bilingual
parity, which is not achieved by translating the English.

---

## B.6 Flagged implementation dependencies

Recorded here rather than resolved, so the owner sees the risk before approving.

1. **Reconcile is claim-based, not document-based — verified.**
   `reconcile` (`bundle.py:1271-1314`) validates the `SurfaceContent` claim
   against the bundle and never parses the rendered document. Relocating a field
   from the business report to the audit layer changes no claim. **The separation
   is a pure presentation change.** No change to the reconcile contract is
   required, and none is proposed.

2. **Caveat set equality is binding.** `bundle.py:1324` — every caveat must be
   claimed. Customer prose is required for all of them; a subset fails closed.

3. **Disclosure is immutable.** `bundle.py:1319-1323` compares it in full.
   It cannot be reworded for tone.

4. **`metric` has no translation hook.** Unlike `label`
   (`GOVERNED_FIGURE_LABELS` → `_row_label`). §B.5's table is new work.

5. **Excel sheet 5 has no governed section.** See §B.4. Recommendation (a)
   avoids new governed analysis.

6. **Chart kinds stay at three.** `GOVERNED_CHART_KINDS`. The waterfall in the
   golden sample is a grouped bar, as `bundle.py:306-314` already documents.

7. **`SECTION_HEADINGS` already exists and is already business-voiced.** The
   section heading path is the one part of this that needs no new mechanism.

8. **Optional delivery is a delivery-layer change, not a generation-layer one.**
   `REQUIRED_SURFACES` is compared for exact equality in six places
   (`bundle.py:1222`, `pipeline.py:156`, `pipeline.py:345`, `reports.py:253`,
   `delivery_persistence.py:349`, `benchmark_trial.py:164`), so all three surfaces
   must always be produced. `delivery_persistence.py:239` already reads surfaces
   back per-surface with an `if surface in found` guard, so withholding one from a
   download needs no contract change. **Do not implement optionality by skipping
   generation.**

9. **The workbook is bilingual and the sample is not.** ~15 sheets delivered
   versus 10 shown. See §B.4. The owner picks suffix-naming (recommended) or
   split workbooks.

10. **Excel sheet 8 (chartdata) must ship with the business workbook** even though
    it is Audit-tier, because `_series_range` (`excel.py:656-665`) addresses it by
    name and the native charts break without it. Hide it rather than omit it.
