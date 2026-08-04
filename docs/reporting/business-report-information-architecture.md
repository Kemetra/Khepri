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

## B.1 Two documents per language, not one

| Layer | Purpose | Audience |
|---|---|---|
| **Business report** | The deliverable. Findings, figures, charts, limitations. | The customer, their staff, their bank |
| **Audit evidence** | The defensibility mechanism. Identifiers, citations, provenance. | An auditor, a sceptical CFO, a dispute |

Both are shipped, always. The audit layer is not optional and not hidden — it is
the product's differentiator. It is *separated* so that the business report reads
as a business report, and *accessible* so the claim "auditable analysis" stays
true.

The business report links to the audit layer once, in the colophon:
"Full calculation evidence and data lineage: see Technical Evidence."

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
    └── Link → Technical Evidence

Technical Evidence  (report.evidence.html)
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
              ── page break, new section ──
Appendix A    Figures and citations
Appendix B    Section states and reason codes
Appendix C    Provenance and versions
```

The appendix begins on a fresh page with its own running header, so a customer
printing "the report" and stopping at the appendix divider has a complete
business document.

**No forked template.** The appendix is a `{% block appendix %}` in the shared
template, empty on the web surface (which links to a separate page instead) and
filled on the print surface. This preserves the DEC-005 single-engine property:
Arabic/English parity, the disclosure, and the figure set stay correct in one
place.

---

## B.4 Excel

Worksheet order **is** the information architecture in a workbook, because it is
what a reader sees on opening. Business sheets first, in reading order; mechanism
sheets last.

| # | Worksheet | Tier | Contents |
|---|---|---|---|
| 1 | Executive Summary | B | Lead finding, hero figure, KPI block, period covered, disclosure |
| 2 | Sales Performance | B | Revenue / units / transactions / average sale by period |
| 3 | Period Comparison | B | Current vs prior, absolute and percentage |
| 4 | Growth Drivers | B | Price effect, volume effect, total change |
| 5 | Product & Category Performance | B | Ranked contribution |
| 6 | Basket Analysis | B | Items per sale, attach rate |
| 7 | Data Limitations | B | Every refusal and caveat in customer prose (§D) |
| 8 | Chart Data | A | Existing chartdata sheet — the one numeric write path (`APP-013`) |
| 9 | Audit Trail | A | section_id, state, raw reason, figure_id, metric, kind, unit_kind, citation_id |
| 10 | Provenance | A | Full BundleIdentity, bundle_id, surface versions |

Business sheets carry **business column names**. No sheet in 1–7 contains a
`figure_id`, `citation_id`, raw `metric`, `kind`, or `unit_kind` column.

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
